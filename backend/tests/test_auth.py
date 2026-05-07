import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import uuid

@pytest.mark.asyncio
async def test_auth_flow():
    # Use random email to avoid duplicate registration issues on multiple test runs
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "secretpassword"
    full_name = "Test User"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Register user
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": full_name
            }
        )
        assert register_response.status_code == 200, register_response.text
        data = register_response.json()
        assert data["email"] == email
        assert data["full_name"] == full_name
        assert "id" in data

        # 2. Duplicate registration should fail
        dup_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": full_name
            }
        )
        assert dup_response.status_code == 400

        # 3. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": email,
                "password": password
            }
        )
        assert login_response.status_code == 200, login_response.text
        token_data = login_response.json()
        assert "access_token" in token_data
        assert "refresh_token" in token_data
        assert token_data["token_type"] == "bearer"

        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]

        # 4. Refresh token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": refresh_token
            }
        )
        assert refresh_response.status_code == 200, refresh_response.text
        new_token_data = refresh_response.json()
        assert "access_token" in new_token_data
        assert "refresh_token" in new_token_data

        # 5. Access protected route with invalid token (should fail)
        bad_auth_response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer invalid_token_value_here"}
        )
        assert bad_auth_response.status_code == 401

        # 6. Access protected route with valid token (should succeed)
        logout_response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert logout_response.status_code == 200
        assert logout_response.json() == {"message": "Successfully logged out"}
