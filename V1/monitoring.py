from fastapi import FastAPI
from fastapi.responses import FileResponse
import pandas as pd
import logging
from typing import Text
from evidently import ColumnMapping
from evidently.report import Report
from evidently.metric_preset import RegressionPreset
from sqlalchemy import create_engine
from sklearn import ensemble
import numpy as np
import webbrowser

app = FastAPI()

# Database connection parameters
DATABASE_URL = "postgresql://your_user:your_password@localhost:5432/your_database"

# Define your data columns
DATA_COLUMNS = {
    'columns': ['datetime', 'open', 'high', 'low', 'close', 'volume', 'previous_close', 'target', 'prediction']
}

def read_data():
    """Read data from PostgreSQL using SQLAlchemy."""
    engine = create_engine(DATABASE_URL)
    query = "SELECT * FROM intraday_data"
    df = pd.read_sql_query(query, engine)
    return df

def load_current_data(window_size: int) -> pd.DataFrame:
    """Load current data from the database."""
    df = read_data()
    current_data = df.tail(window_size)
    return current_data

def load_reference_data(columns: list) -> pd.DataFrame:
    """Load reference data from the database."""
    df = read_data()
    # Ensure the required columns are present and fully populated
    for col in ['target', 'prediction']:
        if col not in df.columns:
            df[col] = np.nan  # or some default value
        else:
            df[col].fillna(method='ffill', inplace=True)  # Forward fill to handle NaNs
    reference_data = df[columns].head(3000)  # Assuming the first 3000 rows are reference data
    return reference_data

def get_column_mapping(**kwargs) -> ColumnMapping:
    column_mapping = ColumnMapping()
    column_mapping.target = 'target'
    column_mapping.prediction = 'prediction'
    column_mapping.numerical_features = ['open', 'high', 'low', 'volume', 'previous_close']
    column_mapping.categorical_features = []
    return column_mapping

def build_model_performance_report(reference_data: pd.DataFrame, current_data: pd.DataFrame, column_mapping: ColumnMapping) -> Text:
    report = Report(metrics=[RegressionPreset()])
    report.run(reference_data=reference_data, current_data=current_data, column_mapping=column_mapping)
    report_path = "model_performance_report.html"
    report.save_html(report_path)
    return report_path

def get_dataset_drift_report(reference_data, current_data, column_mapping):
    # Placeholder function for generating dataset drift report
    report = Report(metrics=[RegressionPreset()])
    report.run(reference_data=reference_data, current_data=current_data, column_mapping=column_mapping)
    return report

def detect_dataset_drift(report):
    # Placeholder function for detecting dataset drift
    return False  # Replace with actual drift detection logic

def get_model_performance_report(reference_data, current_data, column_mapping):
    # Placeholder function for generating model performance report
    report = Report(metrics=[RegressionPreset()])
    report.run(reference_data=reference_data, current_data=current_data, column_mapping=column_mapping)
    return report

def process_data_in_chunks(df):
    """Process the data in chunks of 10,000 records."""
    chunk_size = 10000
    num_chunks = len(df) // chunk_size

    for i in range(num_chunks - 1):
        start_idx_ref = i * chunk_size
        end_idx_ref = start_idx_ref + chunk_size
        start_idx_cur = end_idx_ref
        end_idx_cur = start_idx_cur + chunk_size

        # Reference data
        reference_data = df.iloc[start_idx_ref:end_idx_ref]

        # Current data
        current_data = df.iloc[start_idx_cur:end_idx_cur]

        # Perform drift detection and model performance evaluation
        target = 'close'
        prediction = 'prediction'
        numerical_features = ['open', 'high', 'low', 'volume', 'previous_close']
        categorical_features = []

        regressor = ensemble.RandomForestRegressor(random_state=0, n_estimators=50)
        regressor.fit(reference_data[numerical_features + categorical_features], reference_data[target])
        ref_prediction = regressor.predict(reference_data[numerical_features + categorical_features])
        current_prediction = regressor.predict(current_data[numerical_features + categorical_features])
        
        reference_data['prediction'] = ref_prediction
        current_data['prediction'] = current_prediction

        column_mapping = ColumnMapping()
        column_mapping.target = target
        column_mapping.prediction = prediction
        column_mapping.numerical_features = numerical_features
        column_mapping.categorical_features = categorical_features

        # Generate and detect dataset drift report
        data_drift_report = get_dataset_drift_report(reference_data, current_data, column_mapping)
        drift_detected = detect_dataset_drift(data_drift_report)
    
        if drift_detected:
            print("Dataset drift detected.")
        else:
            print("No dataset drift detected.")

        # Generate and save the dataset drift report
        data_drift_report.save_html(f"data_drift_report_chunk_{i + 1}_to_{i + 2}.html")

        # Generate and save the model performance report
        model_performance_report = get_model_performance_report(reference_data, current_data, column_mapping)
        model_performance_report.save_html(f"model_performance_report_chunk_{i + 1}_to_{i + 2}.html")

        # Open the reports in the default web browser
        webbrowser.open(f"data_drift_report_chunk_{i + 1}_to_{i + 2}.html")
        webbrowser.open(f"model_performance_report_chunk_{i + 1}_to_{i + 2}.html")

@app.get('/monitor-model')
def monitor_model_performance(window_size: int = 3000) -> FileResponse:
    logging.info('Read data from database')
    df = read_data()
    
    # Ensure 'datetime' is a datetime object
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    
    logging.info('Process data in chunks')
    process_data_in_chunks(df)
    
    # Assuming the last chunk's report is the one to return
    report_path = "model_performance_report_chunk_{}_to_{}.html".format(len(df) // 10000 - 1, len(df) // 10000)
    
    logging.info('Return report as html')
    return FileResponse(report_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)