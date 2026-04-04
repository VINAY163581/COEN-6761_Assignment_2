# COEN 6761 - Assignment 2

This repository contains a microservices-based backend system built with Flask, MongoDB, RabbitMQ, and Kong API Gateway.

## Assignment Scope

The implementation demonstrates:

- User service evolution with two versions (`user_service_v1` and `user_service_v2`)
- Weighted traffic routing (strangler/canary-style) between user service versions through Kong
- Order service with create/read/update endpoints
- Event-driven user update propagation to orders using RabbitMQ
- Docker Compose based local orchestration and integration testing

## Tech Stack

- Python 3.10
- Flask + Flask-RESTX
- MongoDB
- RabbitMQ
- Kong Gateway + Konga UI
- Pytest

## Runtime Architecture

Local Docker containers (via `docker-compose.test.yml`):

- `user-service-v1` — POST/PUT user endpoints; publishes RabbitMQ events
- `user-service-v2` — same interface as v1, additionally auto-sets `createdAt`/`updatedAt`
- `order-service` — order CRUD; subscribes to RabbitMQ user-update events
- `kong` — API gateway with strangler-pattern weighted routing
- `konga` — Kong admin UI

Cloud-hosted:

- **MongoDB Atlas** — `userdb` and `orderdb` collections (via `MONGO_URI`)
- **CloudAMQP** — RabbitMQ broker (via `RABBITMQ_URL`, AMQPS)

## Ports

- Kong proxy: `8000`
- Kong admin API: `8001`
- User service v1 (direct): `5002`
- User service v2 (direct): `5003`
- Order service (direct): `5001`
- Konga UI: `1337`

## API Routes (via Kong)

Base URL:

`http://localhost:8000`

User endpoints:

- `POST /users/`
- `PUT /users/{userId}`

Order endpoints:

- `POST /orders/`
- `GET /orders/?status={under process|shipping|delivered}`
- `PUT /orders/{orderId}/status`
- `PUT /orders/{orderId}/details`

## Strangler Pattern Configuration

`P_VALUE` controls user traffic split at the API gateway.

- `USER_SERVICE_V1_WEIGHT = P_VALUE`
- `USER_SERVICE_V2_WEIGHT = 100 - P_VALUE`

Example:

- `P_VALUE=70` routes about 70% to v1 and 30% to v2.

## Data Storage Notes

- User services use `DATABASE_NAME`.
- Order service uses `ORDER_DATABASE_NAME` when provided; otherwise falls back to `orderdb`.
- Mongo credentials in URIs should be URL-encoded if they include reserved characters (for example `@`).

## Setup

### 1. Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Python 3.10+ (only needed to run tests from host)

### 2. Configure Environment

Create/update `.env` in the project root with the required keys:

- `FLASK_APP`
- `FLASK_RUN_PORT`
- `FLASK_RUN_HOST`
- `FLASK_ENV`
- `P_VALUE`
- `RABBITMQ_HOST`
- `RABBITMQ_PORT`
- `RABBITMQ_USER`
- `RABBITMQ_PASSWORD`
- `RABBITMQ_QUEUE_NAME`
- `RABBITMQ_USER_USER`
- `RABBITMQ_USER_PASSWORD`
- `RABBITMQ_ORDER_USER`
- `RABBITMQ_ORDER_PASSWORD`
- `DATABASE_NAME`
- `ORDER_DATABASE_NAME` (optional, defaults to `orderdb`)
- `MONGO_USERNAME`
- `MONGO_PASSWORD`
- `MONGO_URI`

### 3. Start the System

```bash
docker compose down -v
docker compose build
docker compose up -d
```

If you want a clean restart:

```bash
docker compose down -v
docker compose up -d
```

To watch logs:

```bash
docker compose logs -f
```

## Quick API Examples

### Create User

```bash
curl -X POST 'http://localhost:8000/users/' \
    -H 'Content-Type: application/json' \
    -d '{
        "firstName": "John",
        "lastName": "Doe",
        "emails": ["john.doe@example.com"],
        "deliveryAddress": {
            "street": "123 Main Street",
            "city": "Montreal",
            "state": "QC",
            "postalCode": "H1H1H1",
            "country": "Canada"
        },
        "phoneNumber": "5141234567"
    }'
```

### Create Order

```bash
curl -X POST 'http://localhost:8000/orders/' \
    -H 'Content-Type: application/json' \
    -d '{
        "userId": "replace-with-userId",
        "items": [
            {"itemId": "item-101", "quantity": 2, "price": 49.99}
        ],
        "userEmails": ["john.doe@example.com"],
        "deliveryAddress": {
            "street": "123 Main Street",
            "city": "Montreal",
            "state": "QC",
            "postalCode": "H1H1H1",
            "country": "Canada"
        },
        "orderStatus": "under process"
    }'
```

## API Documentation

Swagger/OpenAPI files are available in:

- `docs/swagger/user-swagger.yaml`
- `docs/swagger/order-swagger.yaml`
- `docs/swagger/user-service-swagger.json`
- `docs/swagger/order-service-swagger.json`

Generated HTML docs are available at:

- `docs/swagger/user-service-html-documentation/index.html`
- `docs/swagger/order-service-html-documentation/index.html`

## Testing

### Prerequisites

- Docker Desktop running
- Python 3.10+ with dependencies installed:

```bash
pip install -r requirements.txt
```

- `.env` file present and configured (copy from `.env.example` and fill in values)

### Integration Test Suite

Primary integration test file: `tests/test_services_integration_with_db.py`

Covers four test cases:

| Test Function | Test Case | What it validates |
|---|---|---|
| `test_user_creation` | TC_01 | POST /users/ creates user; verified in MongoDB |
| `test_order_creation` | TC_02 | POST /orders/ creates order referencing a user; verified in MongoDB |
| `test_event_propagation` | TC_03 | PUT /users/{id} triggers RabbitMQ event; linked order updated in MongoDB |
| `test_gateway_routing` | TC_04 | Kong upstream weights match P_VALUE; routing detected via v2 createdAt field |
| `test_user_update` | TC_01 ext. | PUT /users/{id} updates user; MongoDB reflects change |

> **Note:** Each test run generates a unique email suffix (`_RUN_ID`) so the suite is safe to re-run against the persistent MongoDB Atlas database without cleanup.

### Run the Tests

```bash
python3 -m pytest tests/test_services_integration_with_db.py -v
```

The `docker_compose` fixture automatically builds and starts all containers via `docker-compose.test.yml` before any test runs. No manual `docker compose up` is required.

Expected output:

```
collected 5 items

tests/test_services_integration_with_db.py::test_user_creation     PASSED
tests/test_services_integration_with_db.py::test_order_creation    PASSED
tests/test_services_integration_with_db.py::test_event_propagation PASSED
tests/test_services_integration_with_db.py::test_gateway_routing   PASSED
tests/test_services_integration_with_db.py::test_user_update       PASSED

5 passed in ~40s
```

### Changing the Strangler Pattern Split

Edit `P_VALUE` in `.env` before running tests to control routing:

| `P_VALUE` | Traffic to v1 | Traffic to v2 |
|---|---|---|
| `100` | 100% | 0% |
| `50` | 50% | 50% |
| `0` | 0% | 100% |

The Kong container reads `P_VALUE` at build time via the `docker-entrypoint.sh` script, so the fixture's `--build` flag picks up any change automatically.

### Run All Tests

```bash
python3 -m pytest
```

## Useful Commands

```bash
docker compose ps
docker compose logs -f order-service
docker compose logs -f user-service-v1 user-service-v2
docker compose logs -f kong
```


## Repository Layout (Current)

```text
.
├── docker-compose.yml
├── docker-compose.test.yml
├── docs/
├── experiments/
├── src/
│   ├── api_gateway/
│   ├── order_service/
│   ├── shared/
│   ├── user_service_v1/
│   └── user_service_v2/
└── tests/
```
