"""Recoverable model contract errors, distinct from infrastructure/accounting failures."""


class InvalidModelOutput(ValueError):
    """A rejected proposal may be corrected within the caller's existing turn limit."""


class ProviderQuotaExhausted(RuntimeError):
    """Permanent provider quota failure; immediate retries cannot restore credits."""


class ReferenceSelectionError(ValueError):
    """A model chose an unavailable or incorrectly typed reference."""


class ReferenceAuthorizationError(ReferenceSelectionError):
    """This task lacks access; another declared contributor may have full access."""


class ClaimValidationError(ValueError):
    """Model-authored claim defects, safe to feed back without retrying retrieval."""

    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join(f"{i['claim_id']}: {i['message']}" for i in issues))
