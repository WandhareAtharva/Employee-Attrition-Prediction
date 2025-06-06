from flask import Flask, url_for, render_template, request, flash, send_from_directory, jsonify
import pandas as pd
import sys
import os
import json
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from io import BytesIO
import base64

# Add the current directory to path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the prediction function and model variables
from model.model import predict_attrition, pipeline, features, categorical_features, numerical_features
from insights.insights import AttritionAnalyzer

app = Flask(__name__)
app.secret_key = "employee_attrition_prediction"  # For flash messages

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/predict", methods=["GET", "POST"])
def predict():
    prediction = None
    probability = None
    if request.method == "POST":
        try:
            user_data = {}
            print("Received POST request with form data:", request.form)
            for field in request.form:
                val = request.form.get(field)
                if field in numerical_features:
                    try:
                        user_data[field] = [float(val)]
                    except ValueError:
                        flash(f"Invalid value for {field}. Please enter a number.")
                        return render_template("pages/predict_fixed.html")
                else:
                    user_data[field] = [val.strip()]
            
            for feature in features.columns:
                if feature not in user_data:
                    user_data[feature] = [features[feature].median() if feature in numerical_features else features[feature].mode()[0]]

            input_df = pd.DataFrame(user_data)[features.columns]
            pred = predict_attrition(pipeline, input_df)
            prediction = "Yes" if pred.iloc[0] == 1 else "No"
            
            prob = predict_attrition(pipeline, input_df, return_probability=True)
            probability = round(float(prob.iloc[0]) * 100, 2)

        except Exception as e:
            print(f"Error making prediction: {e}")
            flash(f"An error occurred: {e}")
            return render_template("pages/predict_fixed.html")

    return render_template("pages/predict.html", result=prediction is not None, prediction=prediction, probability=probability)


# how to serve css file's folder?
@app.route("/about")
def about():
    return render_template("pages/about.html")

@app.route("/insights")
def insights():
    # Path to the dataset
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/HR-Employee-Attrition.csv")
    
    # Create analyzer instance
    analyzer = AttritionAnalyzer(data_path)
    
    # Get basic summary statistics
    df = pd.read_csv(data_path)
    total_employees = len(df)
    left_count = df[df['Attrition'] == 'Yes'].shape[0]
    stayed_count = total_employees - left_count
    attrition_rate = (left_count / total_employees) * 100
    
    # Generate plots for key relationships
    attrition_by_dept = generate_plot_base64(generate_dept_attrition_plot, df)
    attrition_by_age = generate_plot_base64(generate_age_attrition_plot, df)
    attrition_by_salary = generate_plot_base64(generate_salary_attrition_plot, df)
    attrition_by_overtime = generate_plot_base64(generate_overtime_attrition_plot, df)
    attrition_by_jobrole = generate_plot_base64(generate_jobrole_attrition_plot, df)
    feature_importance = generate_plot_base64(generate_feature_importance_plot, df)
    
    return render_template("pages/insights.html", 
                           total_employees=total_employees,
                           left_count=left_count,
                           stayed_count=stayed_count,
                           attrition_rate=round(attrition_rate, 2),
                           attrition_by_dept=attrition_by_dept,
                           attrition_by_age=attrition_by_age,
                           attrition_by_salary=attrition_by_salary,
                           attrition_by_overtime=attrition_by_overtime,
                           attrition_by_jobrole=attrition_by_jobrole,
                           feature_importance=feature_importance)

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static", path)

# Helper functions to generate plots
def generate_plot_base64(plot_function, df):
    """Generate a base64-encoded plot using the specified function."""
    plt.figure(figsize=(10, 6))
    plot_function(df)
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    
    # Encode the plot to base64
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    return img_str

def generate_dept_attrition_plot(df):
    """Generate a plot showing attrition by department."""
    # Calculate attrition rates by department
    dept_attrition = df.groupby(['Department', 'Attrition']).size().unstack()
    dept_attrition['Total'] = dept_attrition.sum(axis=1)
    dept_attrition['AttritionRate'] = (dept_attrition['Yes'] / dept_attrition['Total']) * 100
    
    # Create the plot
    ax = sns.barplot(x=dept_attrition.index, y=dept_attrition['AttritionRate'])
    plt.title('Attrition Rate by Department', fontsize=14)
    plt.xlabel('Department', fontsize=12)
    plt.ylabel('Attrition Rate (%)', fontsize=12)
    plt.xticks(rotation=45)
    
    # Add value annotations
    for i, v in enumerate(dept_attrition['AttritionRate']):
        ax.text(i, v + 0.5, f"{v:.1f}%", ha='center')

def generate_age_attrition_plot(df):
    """Generate a plot showing attrition by age groups."""
    # Create age bins
    df['AgeGroup'] = pd.cut(df['Age'], bins=[17, 25, 35, 45, 55, 65], labels=['18-25', '26-35', '36-45', '46-55', '56-65'])
    
    # Calculate attrition rates by age group
    age_attrition = df.groupby(['AgeGroup', 'Attrition']).size().unstack()
    age_attrition['Total'] = age_attrition.sum(axis=1)
    age_attrition['AttritionRate'] = (age_attrition['Yes'] / age_attrition['Total']) * 100
    
    # Create the plot
    ax = sns.barplot(x=age_attrition.index, y=age_attrition['AttritionRate'])
    plt.title('Attrition Rate by Age Group', fontsize=14)
    plt.xlabel('Age Group', fontsize=12)
    plt.ylabel('Attrition Rate (%)', fontsize=12)
    
    # Add value annotations
    for i, v in enumerate(age_attrition['AttritionRate']):
        ax.text(i, v + 0.5, f"{v:.1f}%", ha='center')

def generate_salary_attrition_plot(df):
    """Generate a plot showing attrition by salary ranges."""
    # Create salary bins
    df['SalaryGroup'] = pd.cut(df['MonthlyIncome'], 
                               bins=[0, 2000, 5000, 10000, 20000],
                               labels=['<$2K', '$2K-$5K', '$5K-$10K', '>$10K'])
    
    # Calculate attrition rates by salary group
    salary_attrition = df.groupby(['SalaryGroup', 'Attrition']).size().unstack()
    salary_attrition['Total'] = salary_attrition.sum(axis=1)
    salary_attrition['AttritionRate'] = (salary_attrition['Yes'] / salary_attrition['Total']) * 100
    
    # Create the plot
    ax = sns.barplot(x=salary_attrition.index, y=salary_attrition['AttritionRate'])
    plt.title('Attrition Rate by Monthly Income', fontsize=14)
    plt.xlabel('Monthly Income', fontsize=12)
    plt.ylabel('Attrition Rate (%)', fontsize=12)
    
    # Add value annotations
    for i, v in enumerate(salary_attrition['AttritionRate']):
        ax.text(i, v + 0.5, f"{v:.1f}%", ha='center')

def generate_overtime_attrition_plot(df):
    """Generate a plot showing attrition by overtime status."""
    # Calculate attrition rates by overtime
    ot_attrition = df.groupby(['OverTime', 'Attrition']).size().unstack()
    ot_attrition['Total'] = ot_attrition.sum(axis=1)
    ot_attrition['AttritionRate'] = (ot_attrition['Yes'] / ot_attrition['Total']) * 100
    
    # Create the plot
    ax = sns.barplot(x=ot_attrition.index, y=ot_attrition['AttritionRate'])
    plt.title('Attrition Rate by Overtime Status', fontsize=14)
    plt.xlabel('Overtime', fontsize=12)
    plt.ylabel('Attrition Rate (%)', fontsize=12)
    
    # Add value annotations
    for i, v in enumerate(ot_attrition['AttritionRate']):
        ax.text(i, v + 0.5, f"{v:.1f}%", ha='center')
        
def generate_jobrole_attrition_plot(df):
    """Generate a plot showing attrition by job role."""
    # Calculate attrition rates by job role
    role_attrition = df.groupby(['JobRole', 'Attrition']).size().unstack()
    role_attrition['Total'] = role_attrition.sum(axis=1)
    role_attrition['AttritionRate'] = (role_attrition['Yes'] / role_attrition['Total']) * 100
    
    # Sort by attrition rate for better visualization
    role_attrition = role_attrition.sort_values('AttritionRate', ascending=False)
    
    # Create the plot
    ax = sns.barplot(x=role_attrition.index, y=role_attrition['AttritionRate'])
    plt.title('Attrition Rate by Job Role', fontsize=14)
    plt.xlabel('Job Role', fontsize=12)
    plt.ylabel('Attrition Rate (%)', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    
    # Add value annotations
    for i, v in enumerate(role_attrition['AttritionRate']):
        ax.text(i, v + 0.5, f"{v:.1f}%", ha='center')

def generate_feature_importance_plot(df):
    """Generate a plot showing feature importance for attrition."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    
    df_encoded = df.copy() # Work on a copy
    label_encoders = {} # Keep as in original, though not used further in this function

    # Identify all columns that need encoding (object or category dtype)
    # Exclude 'Attrition' as it will be mapped to 0/1 for y
    cols_to_encode = []
    for col_name in df_encoded.columns:
        if col_name == 'Attrition':
            continue
        # Check if dtype is object or category
        if pd.api.types.is_object_dtype(df_encoded[col_name]) or \
           pd.api.types.is_categorical_dtype(df_encoded[col_name]):
            cols_to_encode.append(col_name)
            
    for col in cols_to_encode:
        le = LabelEncoder()
        df_encoded[col] = le.fit_transform(df_encoded[col]) # Corrected: use df_encoded[col]
        label_encoders[col] = le # Keep as in original
        
    # Remove non-predictive columns
    # Add errors='ignore' for robustness if columns are not present
    cols_to_drop_ids = ['EmployeeCount', 'EmployeeNumber', 'StandardHours']
    # Filter for existing columns to avoid KeyError
    existing_cols_to_drop_ids = [col for col in cols_to_drop_ids if col in df_encoded.columns]
    if existing_cols_to_drop_ids:
        df_encoded = df_encoded.drop(columns=existing_cols_to_drop_ids)
        
    # Features and target
    # Ensure 'Attrition' column exists
    if 'Attrition' not in df_encoded.columns:
        # Handle error: e.g., log, raise exception, or display message on plot
        plt.text(0.5, 0.5, "Error: 'Attrition' column missing.", ha='center', va='center', transform=plt.gca().transAxes)
        return

    y = df_encoded['Attrition'].map({'Yes': 1, 'No': 0})
    X = df_encoded.drop(columns=['Attrition'])
    
    # Handle potential NaNs in y after mapping (e.g., if Attrition had unexpected values)
    if y.isnull().any():
        # Remove rows with NaN target to allow model fitting.
        X = X[~y.isnull()]
        y = y[~y.isnull()]
        if X.empty or y.empty:
            plt.text(0.5, 0.5, 'No data after NaN removal for feature plot.', ha='center', va='center', transform=plt.gca().transAxes)
            return

    # Ensure X is not empty before fitting
    if X.empty:
        plt.text(0.5, 0.5, 'No features available for importance plot.', ha='center', va='center', transform=plt.gca().transAxes)
        return
        
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    importances = model.feature_importances_
    
    # Adjust number of features to show if less than 10
    num_features_to_show = min(10, len(X.columns))

    if num_features_to_show == 0: # No features in X
        plt.text(0.5, 0.5, 'No features to plot importance for.', ha='center', va='center', transform=plt.gca().transAxes)
        return
        
    indices = np.argsort(importances)[::-1][:num_features_to_show]
    
    plt.barh(range(len(indices)), importances[indices], align='center')
    plt.yticks(range(len(indices)), [X.columns[i] for i in indices])
    plt.title(f'Top {num_features_to_show} Features for Attrition Prediction', fontsize=14)
    plt.xlabel('Relative Importance', fontsize=12)

if __name__ == "__main__":
    app.run(debug=True)