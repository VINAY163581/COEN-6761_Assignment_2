import os
import pytest
import requests
import pymongo
import pika
import subprocess
import time
from dotenv import load_dotenv

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
    
    # Wait for services to be ready
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

# Fixture for API base URL
@pytest.fixture(scope="module")
def api_base_url():
    return "http://localhost:8000"

# Fixture for MongoDB client
@pytest.fixture(scope="module")
def mongo_client():
    client = pymongo.MongoClient(
        host="localhost", 
        port=27017,
        username=os.getenv("MONGO_USERNAME"),
        password=os.getenv("MONGO_PASSWORD"),
        authSource="admin"
        )
    yield client
    client.close()

# Test: User Creation
def test_user_creation(api_base_url, mongo_client):
    # Create a new user
    user_payload = {
        "firstName": "Integration",
        "lastName": "Tester",
        "emails": ["integration.test@example.com"],
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
    assert user["emails"] == ["integration.test@example.com"]

# Test: User Update
def test_user_update(api_base_url, mongo_client):
    # First create a user
    user_payload = {
        "firstName": "Update",
        "lastName": "Tester",
        "emails": ["update.test@example.com"],
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
    assert old_user["emails"] == ["update.test@example.com"]
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

