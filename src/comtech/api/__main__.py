import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "comtech.api.app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=1,
        access_log=False,
        timeout_graceful_shutdown=10,
    )
