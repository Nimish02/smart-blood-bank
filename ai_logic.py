# Blood Bank Machine Learning Models
# ---------------------------------
# Requirements:
# pip install pandas scikit-learn prophet matplotlib

import pandas as pd
import numpy as np
from prophet import Prophet
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# =====================================================
# PART 1: Forecast Blood Demand using Historical Requests
# =====================================================

# Sample historical blood request data
# Columns: date, requests_count

demand_data = pd.DataFrame({
    "ds": pd.date_range(start="2024-01-01", periods=365, freq="D"),
    "y": np.random.poisson(lam=20, size=365)   # simulated daily demand
})

# Build Prophet model
forecast_model = Prophet()
forecast_model.fit(demand_data)

# Predict next 30 days
future = forecast_model.make_future_dataframe(periods=30)
forecast = forecast_model.predict(future)

print("Blood Demand Forecast:")
print(forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(30))

# Plot forecast
forecast_model.plot(forecast)

# =====================================================
# PART 2: Predict Donor Response Likelihood
# =====================================================

# Sample donor dataset
# Features:
# age
# total_donations
# last_donation_days
# responded_last_campaign
# target = donor responded (1/0)

donor_data = pd.DataFrame({
    "age": np.random.randint(18, 60, 500),
    "total_donations": np.random.randint(1, 15, 500),
    "last_donation_days": np.random.randint(1, 365, 500),
    "responded_last_campaign": np.random.randint(0, 2, 500),
    "response": np.random.randint(0, 2, 500)
})

X = donor_data.drop("response", axis=1)
y = donor_data["response"]

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Logistic Regression Pipeline
model = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", LogisticRegression())
])

model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)

print("\nDonor Response Prediction Accuracy:")
print("Accuracy:", accuracy_score(y_test, y_pred))
print(classification_report(y_test, y_pred))

# =====================================================
# Predict New Donor Probability
# =====================================================

new_donor = pd.DataFrame([{
    "age": 28,
    "total_donations": 5,
    "last_donation_days": 45,
    "responded_last_campaign": 1
}])

prob = model.predict_proba(new_donor)[0][1]

print(f"\nLikelihood donor responds: {prob*100:.2f}%")
