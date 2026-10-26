# tests/test_visitors.py
def test_visitor_self_register_and_verify(client):
    reg_response = client.post(
        "/api/visitors/self-register",
        json={
            "visitorName": "Sundaram Vendor",
            "visitorType": "OTHERS",
            "phoneNumber": "9876543210",
            "reason": "Delivery maintenance",
        },
    )
    assert reg_response.status_code == 200
    reg_data = reg_response.json()
    assert reg_data["success"] is True
    assert "otp" in reg_data
    assert "passNumber" in reg_data

    otp = reg_data["otp"]
    pass_number = reg_data["passNumber"]

    verify_res = client.post(
        "/api/visitors/verify-otp",
        json={"otp": otp, "passNumber": pass_number},
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["success"] is True
