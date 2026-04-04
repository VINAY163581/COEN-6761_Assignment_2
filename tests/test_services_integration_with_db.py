import os
import uuid
import pytest
import requests
import pymongo
import pika
import subprocess
import time
from dotenv import load_dotenv

# Unique run suffix to avoid email-uniqueness conflicts across test runs
_RUN_ID = uuid.uuid4().hex[:8]

# Load environment variables
load_dotenv()

# Fixture to manage Docker Compose
@pytest.fixture(scope="module", autouse=True)
def docker_compose():
    # Start Docker Compose
    subprocess.run(
        ["docker", "compose", "-f", "docker-compose.test.yml", "up", "--build", "-d"],
        check=True
    )

    wait_for_rabbitmq()

    # Wait for Kong admin API to be ready
    wait_for_service("http://localhost:8001/")

    yield  # Run tests

    # Tear down Docker Compose
    # subprocess.run(
    #     ["docker", "compose", "-f", "docker-compose.test.yml", "down", "-v"],
    #     check=True
    # )

# Helper function to wait for service readiness
def wait_for_service(url, timeout=200):
    start = time.time()
    while time.time() - start < timeout:
        try:
            if requests.get(url).status_code == 200:
                return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"Service at {url} not ready")

def wait_for_rabbitmq(timeout=60):
    rabbitmq_url = os.getenv("RABBITMQ_URL")
    start = time.time()
    while time.time() - start < timeout:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
            connection.close()
            return
        except Exception:
            time.sleep(2)
    raise TimeoutError(f"RabbitMQ at {rabbitmq_url} not ready")

# Fixture for API base URL
@pytest.fixture(scope="module")
def api_base_url():
    return "http://localhost:8000"

# Fixture for MongoDB client
@pytest.fixture(scope="module")
def mongo_client():
    client = pymongo.MongoClient(os.getenv("MONGO_URI"))
    yield client
    client.close()

# Test: User Creation
def test_user_creation(api_base_url, mongo_client):
    # Create a new user
    user_payload = {
        "firstName": "Integration",
        "lastName": "Tester",
        "emails": [f"integration.test.{_RUN_ID}@example.com"],
        "deliveryAddress": {
            "street": "123 Test Street",
            "city": "Testville",
            "state": "Test State",
            "postalCode": "12345",
            "country": "Test Country"
        }
    }
    
    # Send user creation request
    response = requests.post(
        f"{api_base_url}/users/", 
        json=user_payload
    )
    
    # Assertions
    assert response.status_code == 201
    created_user = response.json()
    assert created_user['firstName'] == "Integration"
    assert created_user['lastName'] == "Tester"
    
    # Verify user in MongoDB
    users_db = mongo_client[os.getenv("DATABASE_NAME")]
    users_collection = users_db["users"]
    user = users_collection.find_one({"userId": created_user["userId"]})
    assert user is not None
    assert user["emails"] == [f"integration.test.{_RUN_ID}@example.com"]

# Test: Order Creation (TC_02)
def test_order_creation(api_base_url, mongo_client):
    # Create a user first
    user_payload = {
        "firstName": "Order",
        "lastName": "Creator",
        "emails": [f"order.creator.{_RUN_ID}@example.com"],
        "deliveryAddress": {
            "street": "10 Order Lane",
            "city": "OrderCity",
            "state": "Order State",
            "postalCode": "99999",
            "country": "Order Country"
        }
    }
    user_response = requests.post(f"{api_base_url}/users/", json=user_payload)
    assert user_response.status_code == 201
    user_id = user_response.json()["userId"]

    # Create an order referencing the user
    order_payload = {
        "userId": user_id,
        "items": [{"itemId": "ITEM001", "quantity": 2, "price": 29.99}],
        "userEmails": [f"order.creator.{_RUN_ID}@example.com"],
        "deliveryAddress": {
            "street": "10 Order Lane",
            "city": "OrderCity",
            "state": "Order State",
            "postalCode": "99999",
            "country": "Order Country"
        },
        "orderStatus": "under process"
    }
    order_response = requests.post(f"{api_base_url}/orders/", json=order_payload)
    assert order_response.status_code == 201
    created_order = order_response.json()
    order_id = created_order["orderId"]
    assert created_order["userId"] == user_id

    # Verify order persisted in MongoDB
    orders_db = mongo_client["orderdb"]
    orders_collection = orders_db["orders"]
    order = orders_collection.find_one({"orderId": order_id})
    assert order is not None
    assert order["userId"] == user_id
    assert order["orderStatus"] == "under process"


# Test: Event-Driven User Update Propagation (TC_03)
def test_event_propagation(api_base_url, mongo_client):
    # Create a user
    user_payload = {
        "firstName": "Event",
        "lastName": "Propagator",
        "emails": [f"event.propagator.{_RUN_ID}@example.com"],
        "deliveryAddress": {
            "street": "1 Event Street",
            "city": "EventCity",
            "state": "Event State",
            "postalCode": "11111",
            "country": "Event Country"
        }
    }
    user_response = requests.post(f"{api_base_url}/users/", json=user_payload)
    assert user_response.status_code == 201
    user_id = user_response.json()["userId"]

    # Create a linked order
    order_payload = {
        "userId": user_id,
        "items": [{"itemId": "ITEM002", "quantity": 1, "price": 9.99}],
        "userEmails": [f"event.propagator.{_RUN_ID}@example.com"],
        "deliveryAddress": {
            "street": "1 Event Street",
            "city": "EventCity",
            "state": "Event State",
            "postalCode": "11111",
            "country": "Event Country"
        },
        "orderStatus": "under process"
    }
    order_response = requests.post(f"{api_base_url}/orders/", json=order_payload)
    assert order_response.status_code == 201
    order_id = order_response.json()["orderId"]

    # Update the user's email and delivery address
    update_payload = {
        "emails": ["event.updated@example.com"],
        "deliveryAddress": {
            "street": "99 Updated Blvd",
            "city": "UpdatedCity",
            "state": "Updated State",
            "postalCode": "22222",
            "country": "Updated Country"
        }
    }
    update_response = requests.put(f"{api_base_url}/users/{user_id}", json=update_payload)
    assert update_response.status_code == 200

    # Wait for RabbitMQ event to be consumed by the Order Service
    time.sleep(5)

    # Verify the order was updated in MongoDB via the RabbitMQ event
    orders_db = mongo_client["orderdb"]
    orders_collection = orders_db["orders"]
    updated_order = orders_collection.find_one({"orderId": order_id})
    assert updated_order is not None
    assert updated_order["userEmails"] == ["event.updated@example.com"]
    assert updated_order["deliveryAddress"]["street"] == "99 Updated Blvd"
    assert updated_order["deliveryAddress"]["city"] == "UpdatedCity"


# Test: API Gateway Routing - Strangler Pattern (TC_04)
def test_gateway_routing(api_base_url):
    # Verify Kong Admin API is accessible and upstreams are configured
    admin_url = "http://localhost:8001"
    upstream_response = requests.get(f"{admin_url}/upstreams/user_service_upstream/targets")
    assert upstream_response.status_code == 200

    targets = upstream_response.json().get("data", [])
    assert len(targets) == 2, "Expected two upstream targets (v1 and v2)"

    # Map targets to weights
    target_weights = {t["target"]: t["weight"] for t in targets}
    v1_weight = target_weights.get("user-service-v1:5000", 0)
    v2_weight = target_weights.get("user-service-v2:5000", 0)
    assert v1_weight + v2_weight == 100, "Total upstream weight must equal 100"

    # Send requests through Kong and detect which version handles them
    # V2 sets 'createdAt' automatically; V1 does not
    v1_count = 0
    v2_count = 0
    num_requests = 10
    for i in range(num_requests):
        payload = {
            "firstName": "GW",
            "lastName": f"RouteTest{i}",
            "emails": [f"gateway.route.test.{_RUN_ID}.{i}@example.com"],
            "deliveryAddress": {
                "street": f"{i} Gateway Rd",
                "city": "GatewayCity",
                "state": "GW State",
                "postalCode": "33333",
                "country": "GW Country"
            }
        }
        resp = requests.post(f"{api_base_url}/users/", json=payload)
        assert resp.status_code == 201
        if resp.json().get("createdAt"):
            v2_count += 1
        else:
            v1_count += 1

    # Validate routing distribution matches configured weights
    # With P_VALUE=100 (v1_weight=100, v2_weight=0), all should go to v1
    # With P_VALUE=0 (v1_weight=0, v2_weight=100), all should go to v2
    # With P_VALUE=50, approximately half to each (within 30% tolerance for 10 requests)
    if v1_weight == 100:
        assert v1_count == num_requests, f"Expected all {num_requests} requests to v1, got {v1_count}"
    elif v2_weight == 100:
        assert v2_count == num_requests, f"Expected all {num_requests} requests to v2, got {v2_count}"
    else:
        # Mixed: verify neither version gets 0 traffic (within tolerance)
        tolerance = 0.3 * num_requests
        expected_v1 = num_requests * v1_weight / 100
        assert abs(v1_count - expected_v1) <= tolerance, (
            f"v1 got {v1_count} requests, expected ~{expected_v1} (±{tolerance})"
        )


# Test: User Update
def test_user_update(api_base_url, mongo_client):
    # First create a user
    user_payload = {
        "firstName": "Update",
        "lastName": "Tester",
        "emails": [f"update.test.{_RUN_ID}@example.com"],
        "deliveryAddress": {
            "street": "123 Test Street",
            "city": "Testville",
            "state": "Test State",
            "postalCode": "12345",
            "country": "Test Country"
        }
    }
    
    # Create user
    create_response = requests.post(
        f"{api_base_url}/users/", 
        json=user_payload
    )
    
    assert create_response.status_code == 201
    created_user = create_response.json()
    user_id = created_user["userId"]
    
    # Update the user
    update_payload = {
        "emails": ["updated.email@example.com"],
        "deliveryAddress": {
            "street": "456 Update Street",
            "city": "Updateville",
            "state": "Update State",
            "postalCode": "54321",
            "country": "Update Country"
        }
    }
    
    # Send update request
    update_response = requests.put(
        f"{api_base_url}/users/{user_id}", 
        json=update_payload
    )
    
    # Assertions for the response
    assert update_response.status_code == 200
    update_result = update_response.json()
    
    # The response should contain both old and new user data
    old_user = update_result[0]
    new_user = update_result[1]
    
    # Check old user data
    assert old_user["emails"] == [f"update.test.{_RUN_ID}@example.com"]
    assert old_user["deliveryAddress"]["street"] == "123 Test Street"
    
    # Check new user data
    assert new_user["emails"] == ["updated.email@example.com"]
    assert new_user["deliveryAddress"]["street"] == "456 Update Street"
    assert new_user["deliveryAddress"]["city"] == "Updateville"
    
    # Verify update in MongoDB
    users_db = mongo_client[os.getenv("DATABASE_NAME")]
    users_collection = users_db["users"]
    updated_user = users_collection.find_one({"userId": user_id})
    assert updated_user is not None
    assert updated_user["emails"] == ["updated.email@example.com"]
    assert updated_user["deliveryAddress"]["street"] == "456 Update Street"

