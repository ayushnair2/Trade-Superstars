"""Create all tables defined in app.models. Run: python -m app.create_tables"""

from app.db import Base, engine
from app import models  # noqa: F401  -- imported so models register on Base.metadata


def main() -> None:
    Base.metadata.create_all(engine)
    print("Created tables:", ", ".join(sorted(Base.metadata.tables)))


if __name__ == "__main__":
    main()
