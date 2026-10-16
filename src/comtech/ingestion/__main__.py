import argparse
import json

from openai import APIError

from comtech.settings import Settings

from .hosted import Build, PineconeDocuments, ProviderError
from .prepare import prepare


def main():
    parser = argparse.ArgumentParser(description="Prepare and ingest the Northstar corpus")
    parser.add_argument(
        "stage", choices=["prepare", "preflight", "embed", "upload", "verify", "publish", "run"]
    )
    parser.add_argument("--build")
    args = parser.parse_args()
    settings = Settings()
    if args.stage in ("prepare", "run"):
        result = prepare(settings)
        print(json.dumps(result, indent=2), flush=True)
        args.build = result["build_id"]
        if args.stage == "prepare":
            return
    if not args.build:
        parser.error("--build is required for this stage")
    build = Build(settings, args.build)
    if args.stage == "publish":
        build.publish()
        return
    pinecone = PineconeDocuments(settings)
    try:
        if args.stage in ("preflight", "embed", "run"):
            build.preflight(pinecone)
        if args.stage in ("embed", "run"):
            print(json.dumps(build.embed()), flush=True)
        if args.stage in ("upload", "run"):
            build.upload(pinecone)
        if args.stage in ("verify", "run"):
            build.verify(pinecone)
        if args.stage == "run":
            build.publish()
    finally:
        pinecone.close()


if __name__ == "__main__":
    try:
        main()
    except APIError as error:
        raise SystemExit(
            f"OpenAI {type(error).__name__}, HTTP "
            f"{getattr(error, 'status_code', 'connection failure')}; "
            "check model access, billing and limits. Cached progress is retained."
        ) from None
    except (ProviderError, ValueError) as error:
        raise SystemExit(str(error)) from None
