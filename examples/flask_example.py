"""Flask middleware example for LogWard Python SDK."""

from flask import Flask

from logward_sdk import ClientOptions, LogWardClient
from logward_sdk.middleware import LogWardFlaskMiddleware

app = Flask(__name__)

# Initialize LogWard client
client = LogWardClient(
    ClientOptions(
        api_url="http://localhost:8080",
        api_key="lp_your_api_key_here",
    )
)

# Add middleware
LogWardFlaskMiddleware(
    app,
    client=client,
    service_name="flask-api",
    log_requests=True,
    log_responses=True,
    log_errors=True,
    include_headers=False,
    include_body=False,
    skip_health_check=True,
    skip_paths=["/metrics"],
)


@app.route("/")
def index():
    return {"message": "Hello from Flask!"}


@app.route("/users/<int:user_id>")
def get_user(user_id):
    return {"id": user_id, "name": "John Doe"}


@app.route("/error")
def error_route():
    raise ValueError("Test error")


if __name__ == "__main__":
    app.run(port=3000)
