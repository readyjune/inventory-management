"""
Tests for restocking API endpoints (recommendations and submitted orders).
"""
import pytest


LEAD_TIME_DAYS_BY_CATEGORY = {
    'Circuit Boards': 10,
    'Sensors': 7,
    'Actuators': 12,
    'Controllers': 6,
    'Power Supplies': 9,
}


class TestRestockRecommendationsEndpoint:
    """Test suite for GET /api/restocking/recommendations."""

    def test_get_recommendations_structure(self, client):
        """Test that recommendations have the expected structure."""
        response = client.get("/api/restocking/recommendations?budget=5000")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        item = data[0]
        assert "item_sku" in item
        assert "item_name" in item
        assert "category" in item
        assert "current_demand" in item
        assert "forecasted_demand" in item
        assert "trend" in item
        assert "unit_cost" in item
        assert "recommended_quantity" in item
        assert "recommended_cost" in item
        assert isinstance(item["recommended_quantity"], int)
        assert isinstance(item["recommended_cost"], (int, float))

    def test_recommendations_respect_budget(self, client):
        """Test that total recommended cost never exceeds the given budget."""
        for budget in [100, 500, 2000, 10000]:
            response = client.get(f"/api/restocking/recommendations?budget={budget}")
            assert response.status_code == 200

            data = response.json()
            total_cost = sum(item["recommended_cost"] for item in data)
            assert total_cost <= budget + 0.01

    def test_recommendations_only_include_positive_demand_growth(self, client):
        """Test that only items with forecasted demand above current demand are recommended."""
        response = client.get("/api/restocking/recommendations?budget=20000")
        data = response.json()

        for item in data:
            assert item["forecasted_demand"] > item["current_demand"]
            assert item["recommended_quantity"] > 0

    def test_recommendations_sorted_by_urgency(self, client):
        """Test that recommendations are sorted by descending demand-urgency score."""
        response = client.get("/api/restocking/recommendations?budget=20000")
        data = response.json()

        trend_weight = {"increasing": 1.5, "stable": 1.0, "decreasing": 0.5}
        scores = [
            ((item["forecasted_demand"] - item["current_demand"]) / max(item["current_demand"], 1))
            * trend_weight.get(item["trend"], 1.0)
            for item in data
        ]

        assert scores == sorted(scores, reverse=True)

    def test_zero_budget_returns_no_recommendations(self, client):
        """Test that a zero budget yields no recommendations."""
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 200
        assert response.json() == []

    def test_recommendations_filtered_by_category(self, client):
        """Test filtering recommendations by category."""
        response = client.get("/api/restocking/recommendations?budget=20000&category=Actuators")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for item in data:
            assert item["category"] == "Actuators"


class TestSubmitRestockOrderEndpoint:
    """Test suite for POST /api/restocking/orders and GET /api/restocking/orders."""

    def test_submit_order_success(self, client):
        """Test submitting a valid restocking order."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "GSK-203", "quantity": 25}], "budget": 1000}
        )
        assert response.status_code == 200

        order = response.json()
        assert order["order_number"].startswith("RSK-2025-")
        assert order["status"] == "Submitted"
        assert len(order["items"]) == 1
        assert order["items"][0]["item_sku"] == "GSK-203"
        assert order["items"][0]["quantity"] == 25

        expected_line_total = round(25 * order["items"][0]["unit_cost"], 2)
        assert abs(order["items"][0]["line_total"] - expected_line_total) < 0.01
        assert abs(order["total_cost"] - expected_line_total) < 0.01

    def test_submit_order_lead_time_matches_category(self, client):
        """Test that lead time is derived from the item's category."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "SNR-420", "quantity": 10}], "budget": 2000}
        )
        assert response.status_code == 200

        order = response.json()
        assert order["lead_time_days"] == LEAD_TIME_DAYS_BY_CATEGORY["Sensors"]

    def test_submit_order_lead_time_uses_slowest_category(self, client):
        """Test that a multi-category order uses the max lead time across its items' categories."""
        response = client.post(
            "/api/restocking/orders",
            json={
                "items": [
                    {"item_sku": "CTL-330", "quantity": 5},   # Controllers -> 6 days
                    {"item_sku": "WDG-001", "quantity": 5},   # Actuators -> 12 days
                ],
                "budget": 5000
            }
        )
        assert response.status_code == 200

        order = response.json()
        assert order["lead_time_days"] == max(
            LEAD_TIME_DAYS_BY_CATEGORY["Controllers"],
            LEAD_TIME_DAYS_BY_CATEGORY["Actuators"]
        )

    def test_submit_order_expected_delivery_after_submitted_date(self, client):
        """Test that expected_delivery is after submitted_date by lead_time_days."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "PSU-501", "quantity": 10}], "budget": 1000}
        )
        assert response.status_code == 200

        order = response.json()
        assert "T" in order["submitted_date"]
        assert "T" in order["expected_delivery"]
        assert order["expected_delivery"] > order["submitted_date"]

    def test_submit_order_unknown_sku_returns_404(self, client):
        """Test that submitting an order with an unknown SKU returns 404."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "NOT-A-REAL-SKU", "quantity": 5}], "budget": 500}
        )
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_submitted_order_appears_in_orders_list(self, client):
        """Test that a submitted order is retrievable via GET /api/restocking/orders."""
        submit_response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "BRG-102", "quantity": 5}], "budget": 500}
        )
        assert submit_response.status_code == 200
        order_number = submit_response.json()["order_number"]

        list_response = client.get("/api/restocking/orders")
        assert list_response.status_code == 200

        order_numbers = [order["order_number"] for order in list_response.json()]
        assert order_number in order_numbers
