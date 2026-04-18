from fastapi import APIRouter
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

router = APIRouter()

# ─────────────────────────────────────────────
# ROUTE 1: Predict Blood Demand
# ─────────────────────────────────────────────

@router.get("/predict_demand", tags=["AI"])
def predict_demand():
    """Forecast blood demand for next 30 days"""
    
    # Simulated historical data
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=365, freq="D")
    demand = np.random.poisson(lam=20, size=365)
    
    # Simple moving average forecast
    avg_demand = int(np.mean(demand))
    trend = int(np.polyfit(range(365), demand, 1)[0])
    
    forecast = []
    for i in range(30):
        predicted = max(0, avg_demand + (trend * i))
        forecast.append({
            "day": i + 1,
            "date": str(pd.Timestamp.today() + pd.Timedelta(days=i+1))[:10],
            "predicted_requests": predicted
        })
    
    return {
        "average_daily_demand": avg_demand,
        "trend": "increasing" if trend > 0 else "decreasing",
        "forecast": forecast
    }


# ─────────────────────────────────────────────
# ROUTE 2: Predict Donor Response
# ─────────────────────────────────────────────

@router.get("/predict_donor_response", tags=["AI"])
def predict_donor_response(
    age: int = 28,
    total_donations: int = 5,
    last_donation_days: int = 45,
    responded_last_campaign: int = 1
):
    """Predict likelihood of a donor responding to a campaign"""
    
    # Train model on sample data
    np.random.seed(42)
    donor_data = pd.DataFrame({
        "age": np.random.randint(18, 60, 500),
        "total_donations": np.random.randint(1, 15, 500),
        "last_donation_days": np.random.randint(1, 365, 500),
        "responded_last_campaign": np.random.randint(0, 2, 500),
        "response": np.random.randint(0, 2, 500)
    })

    X = donor_data.drop("response", axis=1)
    y = donor_data["response"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression())
    ])
    model.fit(X_train, y_train)

    # Predict for given donor
    new_donor = pd.DataFrame([{
        "age": age,
        "total_donations": total_donations,
        "last_donation_days": last_donation_days,
        "responded_last_campaign": responded_last_campaign
    }])

    prob = model.predict_proba(new_donor)[0][1]

    return {
        "age": age,
        "total_donations": total_donations,
        "last_donation_days": last_donation_days,
        "likelihood_percent": round(prob * 100, 2),
        "will_respond": bool(prob >= 0.5),
        "recommendation": "Contact this donor" if prob >= 0.5 else "Low priority donor"
    }