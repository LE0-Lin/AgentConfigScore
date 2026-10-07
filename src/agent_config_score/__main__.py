"""Run the same product entrypoint without relying on shell PATH setup."""

from .entrypoint import main


if __name__ == "__main__":
    raise SystemExit(main())
