from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

test_cases = [
    # 1. Pure Tanglish OTP (words written in English letters)
    ("student OTP ezhu naalu anju ezhu naalu moonu check pannu", "VERIFY_OTP", "745743"),
    # 2. Tanglish with 'onnu rendu moonu'
    ("OTP onnu rendu moonu naalu anju aaru", "VERIFY_OTP", "123456"),
    # 3. Mixed English + Tamil script + Tanglish
    ("student OTP ezhu 4 அஞ்சு 7 naalu three", "VERIFY_OTP", "745743"),
    # 4. Tanglish with 'double'
    ("OTP double ezhu four five seven four three", "VERIFY_OTP", "774574"),
    # 5. Pure Tamil script OTP
    ("OTP ஏழு நான்கு ஐந்து ஏழு நான்கு மூன்று", "VERIFY_OTP", "745743"),
    # 6. Tanglish Exit confirmation
    ("gate open pannu student veliya pogalam", "CONFIRM_EXIT", None),
    # 7. Tanglish Missing ID incident
    ("id card illama student gate jump panna try pandran stop pannom", "LOG_INCIDENT", None),
    # 8. Tanglish Medical emergency incident
    ("main gate la oru student faint aagi vizhunthutan udambu sariyilla", "LOG_INCIDENT", None),
    # 9. Tanglish Dispute incident
    ("student gate la sanda pottu thagaraaru pandraanga", "LOG_INCIDENT", None),
    # 10. Tanglish Parent Checkout
    ("parent kooda student poran permission ketanga", "LOG_INCIDENT", None)
]

print("=== TESTING MULTI-LINGUAL VOICE ENGINE (TAMIL + TANGLISH + ENGLISH) ===")
for i, (phrase, expected_intent, expected_otp) in enumerate(test_cases, 1):
    res = client.post("/api/v1/gatepass/voice-command", json={"transcript": phrase})
    assert res.status_code == 200, f"Failed on: {phrase}"
    data = res.json()
    intent = data.get("intent")
    otp = data.get("extracted_otp")
    assert intent == expected_intent, f"Expected {expected_intent}, got {intent} on: {phrase}"
    if expected_otp:
        assert otp == expected_otp, f"Expected OTP {expected_otp}, got {otp} on: {phrase}"
    print(f"Test {i} PASSED: '{phrase}' -> Intent: {intent}, OTP: {otp}")

print("\nALL 10 MULTI-LINGUAL (TAMIL + TANGLISH + ENGLISH) TESTS PASSED SUCCESSFULLY (CODE 0)!")
