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

Main services defined in Docker Compose:

- `mongodb` (Mongo database)
- `mongodb-setup` (schema setup + seed script)
- `user-service-v1`
- `user-service-v2`
- `order-service`
- `kong` (API gateway)
- `konga` (gateway UI)

RabbitMQ is defined in a separate Compose file so it appears as its own Docker Desktop project named `rabbitmq`:

- `docker-compose.rabbitmq.yml`

## Ports

- Kong proxy: `8000`
- Kong admin API: `8001`
- User service v1 (direct): `5002`
- User service v2 (direct): `5003`
- Order service (direct): `5001`
- MongoDB: `27017`
- RabbitMQ AMQP: `5673`
- RabbitMQ management UI: `15672`
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

Start RabbitMQ separately when you want it outside the main stack:

```bash
docker compose -f docker-compose.rabbitmq.yml up -d
```

If you want a clean restart of both projects:

```bash
docker compose down -v
docker compose -f docker-compose.rabbitmq.yml down -v
docker compose up -d
docker compose -f docker-compose.rabbitmq.yml up -d
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

Primary integration test:

- `tests/test_services_integration_with_db.py`

Run tests from host:

```bash
python -m pytest tests/test_services_integration_with_db.py
```

Or run all tests configured by `pytest.ini`:

```bash
pytest
```

The integration test starts `docker-compose.rabbitmq.yml` and `docker-compose.test.yml` automatically.

## Useful Commands

```bash
docker compose ps
docker compose logs -f order-service
docker compose logs -f user-service-v1 user-service-v2
docker compose logs -f kong
```

For the separate RabbitMQ project, use:

```bash
docker compose -f docker-compose.rabbitmq.yml logs -f
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
