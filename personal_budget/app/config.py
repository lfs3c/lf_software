import os


class Settings:
    app_name = "Personal Budget"
    secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@db:5432/personal_budget",
    )


settings = Settings()
