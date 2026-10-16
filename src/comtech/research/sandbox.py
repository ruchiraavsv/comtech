"""Linux kernel boundary, installed before executing any generated code."""

import ctypes
import errno
import os
import resource
from pathlib import Path


def restrict_files(libc):
    """Landlock ABI 3: all filesystem mutations are confined to this job's workspace."""
    if libc.syscall(444, 0, 0, 1) < 3:
        raise RuntimeError("Landlock ABI 3 is required")

    class Ruleset(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]

    class Rule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]

    writes = sum(1 << n for n in (1, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14))
    ruleset = libc.syscall(444, ctypes.byref(Ruleset(writes)), 8, 0)
    if ruleset < 0:
        raise OSError(ctypes.get_errno(), "Cannot create Landlock rules")
    directory = os.open(".", os.O_PATH | os.O_CLOEXEC)
    try:
        rule = Rule(writes, directory)
        if libc.syscall(445, ruleset, 1, ctypes.byref(rule), 0) != 0:
            raise OSError(ctypes.get_errno(), "Cannot restrict filesystem")
        if libc.syscall(446, ruleset, 0) != 0:
            raise OSError(ctypes.get_errno(), "Cannot enforce filesystem boundary")
    finally:
        os.close(directory)
        os.close(ruleset)


def restrict(limits):
    # RLIMIT_NPROC is UID-wide across containers sharing the host user namespace.
    # UID 10001 belongs to the API/UI/MCP services; their threads must not consume
    # generated code's independent 16-task allowance.
    if os.getuid() != 10002 or os.getgid() != 10002:
        raise RuntimeError("Generated code requires its dedicated UID/GID")
    libc = ctypes.CDLL(None, use_errno=True)

    class Header(ctypes.Structure):
        _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]

    class Caps(ctypes.Structure):
        _fields_ = [
            ("effective", ctypes.c_uint32),
            ("permitted", ctypes.c_uint32),
            ("inheritable", ctypes.c_uint32),
        ]

    if libc.capset(ctypes.byref(Header(0x20080522, 0)), (Caps * 2)()) != 0:
        raise OSError(ctypes.get_errno(), "Unable to clear capabilities")
    for option, value in ((38, 1), (4, 0)):  # NO_NEW_PRIVS; DUMPABLE
        if libc.prctl(option, value, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "Unable to restrict process")
    if len(os.listdir("/proc/self/task")) != 1:
        raise RuntimeError("Numerical libraries must initialize without background threads")
    restrict_files(libc)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (limits["cpu_seconds"], limits["cpu_seconds"]))
    resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024**2, 32 * 1024**2))
    lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    context = lib.seccomp_init(0x7FFF0000)  # ALLOW; stack on the runtime's default profile.
    if not context:
        raise RuntimeError("seccomp is unavailable")
    denied = (
        "socket",
        "socketpair",
        "connect",
        "bind",
        "listen",
        "accept",
        "accept4",
        "fork",
        "vfork",
        "execve",
        "execveat",
        "ptrace",
        "process_vm_readv",
        "process_vm_writev",
        "pidfd_getfd",
        "kill",
        "tkill",
        "tgkill",
        "pidfd_send_signal",
        "mount",
        "umount2",
        "pivot_root",
        "chroot",
        "unshare",
        "setns",
        "bpf",
        "userfaultfd",
        "io_uring_setup",
        "keyctl",
        "add_key",
        "request_key",
        "open_by_handle_at",
        "reboot",
        "kexec_load",
        "init_module",
        "finit_module",
    )
    try:

        class Comparison(ctypes.Structure):
            _fields_ = [
                ("arg", ctypes.c_uint),
                ("op", ctypes.c_uint),
                ("a", ctypes.c_uint64),
                ("b", ctypes.c_uint64),
            ]

        lib.seccomp_rule_add_array.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.POINTER(Comparison),
        ]
        # Only same-process threads may use clone. They inherit every filter/Landlock rule
        # and the UID-wide 16-task ceiling; killing the process also kills its threads.
        comparison = Comparison(0, 7, 0x10000, 0)  # CLONE_THREAD absent
        clone = lib.seccomp_syscall_resolve_name(b"clone")
        if (
            lib.seccomp_rule_add_array(
                context, 0x00050000 | errno.EPERM, clone, 1, ctypes.byref(comparison)
            )
            != 0
        ):
            raise RuntimeError("Cannot restrict process creation")
        for name in (*denied, "clone3"):
            syscall = lib.seccomp_syscall_resolve_name(name.encode())
            if syscall < 0:
                raise RuntimeError("Unknown restricted syscall: " + name)
            error = errno.ENOSYS if name == "clone3" else errno.EPERM
            if lib.seccomp_rule_add(context, 0x00050000 | error, syscall, 0) != 0:
                raise RuntimeError("Cannot install syscall restriction")
        if lib.seccomp_load(context) != 0:
            raise RuntimeError("Cannot load seccomp filter")
    finally:
        lib.seccomp_release(context)


def restrict_memory(limits):
    # Native-library mappings exist before this ceiling; all imports are already isolated
    # by seccomp/Landlock and the container's physical-memory/CPU/PID limits.
    status = Path("/proc/self/status").read_text()
    baseline = int(next(x.split()[1] for x in status.splitlines() if x.startswith("VmSize:")))
    maximum = baseline * 1024 + limits["memory_bytes"]
    resource.setrlimit(resource.RLIMIT_AS, (maximum, maximum))


def assert_container():
    """Fail closed when accidentally launched on a host or with weaker deployment flags."""
    if os.getuid() != 10000 or os.getpid() != 1:
        raise RuntimeError("Runner must be container PID 1 under supervisor UID 10000")
    status = Path("/proc/self/status").read_text()
    values = dict(x.split(":", 1) for x in status.splitlines() if ":" in x)
    if values["NoNewPrivs"].strip() != "1" or values["Seccomp"].strip() != "2":
        raise RuntimeError("Container security profile missing")
    if set(os.listdir("/sys/class/net")) != {"lo"}:
        raise RuntimeError("Runner requires network_mode: none")
    for file, maximum in (("memory.max", 2 * 1024**3), ("pids.max", 64)):
        value = Path("/sys/fs/cgroup", file).read_text().strip()
        if value == "max" or int(value) > maximum:
            raise RuntimeError("Container resource limit missing: " + file)
    quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
    if quota == "max" or int(quota) > 2 * int(period):
        raise RuntimeError("Container CPU limit missing")
