import streamlit as st
import pandas as pd
import numpy as np

# Load historical data from Google Sheets
CUSTOMER_DATA_URL = "https://docs.google.com/spreadsheets/d/1cCjvCal_UaPfWVN5YUhrryQBTmOMEXBfK_sb55X0pJQ/export?format=csv&gid=0"
JEEPNEY_DATA_URL = "https://docs.google.com/spreadsheets/d/1cCjvCal_UaPfWVN5YUhrryQBTmOMEXBfK_sb55X0pJQ/export?format=csv&gid=0"

# Function to convert time strings (MM:SS) to minutes as floats
def convert_to_minutes(time_str):
    try:
        mins, secs = map(int, time_str.split(':'))
        return mins + secs / 60
    except ValueError:
        return 0  # Handle invalid or missing values gracefully

# Load datasets
def load_data():
    customer_data = pd.read_csv(CUSTOMER_DATA_URL)
    jeepney_data = pd.read_csv(JEEPNEY_DATA_URL)
    return customer_data, jeepney_data

# Preprocess data to calculate probabilities and handle time conversions
def preprocess_data(customer_data, jeepney_data):
    # Convert time strings to minutes
    customer_data["Arrival Time (mins)"] = customer_data["Arrival Time (mins)"].apply(convert_to_minutes)
    jeepney_data["Interarrival in mins"] = jeepney_data["Interarrival in mins"].apply(convert_to_minutes)
    
    # Calculate reneging probabilities
    customer_data["Reneging Rate"] = customer_data["No of Reneged"] / customer_data["No of Customer Arrived"]
    
    # Calculate jeepney statistics
    jeepney_stats = {
        "interarrival_mean": jeepney_data["Interarrival in mins"].mean(),
        "boarding_mean": jeepney_data["Number of Passengers Boarded"].mean(),
        "stopped_prob": jeepney_data["Jeepney came from phase 3 but stopped"].mean(),
        "no_passengers_prob": jeepney_data["Jeepney arrived without passengers onboard"].mean()
    }
    return customer_data, jeepney_stats

# Updated Simulation logic
def run_simulation(customer_data, jeepney_stats, simulation_time, num_replications):
    results = []
    individual_replications = {}

    for replication in range(num_replications):
        np.random.seed(replication)  # Use unique seed for each replication
        time = 0
        customers_waiting = 0
        customers_served = 0
        customers_reneged = 0
        total_wait_time = 0
        jeepney_arrivals = 0
        jeepney_utilization_time = 0

        # Individual replication details
        events = []

        for _, row in customer_data.iterrows():
            # Simulate customer arrival
            time += float(row["Arrival Time (mins)"])
            if time > simulation_time:
                break
            customers_arrived = int(row["No of Customer Arrived"])
            reneging_rate = row["Reneging Rate"]

            # Simulate reneging behavior
            for _ in range(customers_arrived):
                if np.random.rand() < reneging_rate:
                    customers_reneged += 1
                else:
                    customers_waiting += 1

            # Log customer arrival
            events.append({
                "Event": "Customer Arrived",
                "Time (mins)": time,
                "Customers Arrived": customers_arrived,
                "Reneged": customers_reneged,
                "Customers Waiting": customers_waiting,
            })

            # Simulate jeepney arrivals and boarding
            while customers_waiting > 0:
                jeepney_arrivals += 1
                interarrival_time = np.random.exponential(jeepney_stats["interarrival_mean"])
                time += interarrival_time
                if time > simulation_time:
                    break

                # Simulate passengers boarding
                num_served = min(customers_waiting, np.random.poisson(jeepney_stats["boarding_mean"]))
                customers_served += num_served
                total_wait_time += num_served * interarrival_time
                customers_waiting -= num_served
                jeepney_utilization_time += num_served

                # Log jeepney arrival, boarding, and departure
                events.append({
                    "Event": "Jeepney Arrived",
                    "Time (mins)": time,
                    "Customers Served": num_served,
                    "Customers Waiting": customers_waiting,
                    "Jeepney Departure Time": time,  # Log departure time as the same as arrival time
                    "Customers Boarded": num_served,
                })

        # Store detailed events for this replication
        individual_replications[replication + 1] = pd.DataFrame(events)

        # Store aggregated results for this replication
        results.append({
            "Replication": replication + 1,
            "Customers Arrived": customers_served + customers_reneged,
            "Customers Served": customers_served,
            "Customers Reneged": customers_reneged,
            "Jeepneys Arrived": jeepney_arrivals,
            "Average Wait Time (mins)": total_wait_time / customers_served if customers_served > 0 else 0,
            "Utilization Rate": jeepney_utilization_time / (jeepney_arrivals * jeepney_stats["boarding_mean"]) if jeepney_arrivals > 0 else 0
        })

    # Compute overall metrics
    total_customers = customer_data["No of Customer Arrived"].sum()
    reneging_rate = customer_data["No of Reneged"].sum() / total_customers if total_customers > 0 else 0
    jeepney_utilization_rate = jeepney_utilization_time / (jeepney_arrivals * jeepney_stats["boarding_mean"]) if jeepney_arrivals > 0 else 0

    metrics = {
        "Total Customers Arrived": total_customers,
        "Total Customers Served": customers_served,
        "Total Customers Reneged": customers_reneged,
        "Reneging Rate": reneging_rate,
        "Total Jeepneys Arrived": jeepney_arrivals,
        "Jeepney Utilization Rate": jeepney_utilization_rate
    }

    return pd.DataFrame(results), metrics, individual_replications

# Streamlit App
def main():
    st.title("Jeepney and Customer Simulation")

    # Sidebar for Simulation Parameters
    st.sidebar.header("Simulation Parameters")
    
    # Simulation Parameters
    st.sidebar.subheader("Simulation Setup")
    num_replications = st.sidebar.slider("Number of Replications", 1, 50, 10)
    simulation_time = st.sidebar.slider("Total Simulation Time (mins)", 30, 240, 120)

    # Load and preprocess data
    customer_data, jeepney_data = load_data()
    customer_data, jeepney_stats = preprocess_data(customer_data, jeepney_data)

    # Run the Simulation
    results_df, metrics, individual_replications = run_simulation(customer_data, jeepney_stats, simulation_time, num_replications)

    # Tabs for Different Views
    tab1, tab2 = st.tabs(["Simulation Results", "Detailed Replication Events"])

    # Tab 1: Simulation Results
    with tab1:
        st.subheader("Simulation Results")

        # Simulation Table
        st.write("**Detailed Replication Results:**")
        st.dataframe(results_df)

        # Simulation Metrics
        st.write("**Aggregate Metrics:**")
        st.write(f"Total Customers Arrived: {metrics['Total Customers Arrived']}")
        st.write(f"Total Customers Served: {metrics['Total Customers Served']}")
        st.write(f"Total Customers Reneged: {metrics['Total Customers Reneged']}")
        st.write(f"Reneging Rate: {metrics['Reneging Rate']:.2%}")
        st.write(f"Total Jeepneys Arrived: {metrics['Total Jeepneys Arrived']}")
        st.write(f"Jeepney Utilization Rate: {metrics['Jeepney Utilization Rate']:.2%}")

    # Tab 2: Detailed Replication Events
    with tab2:
        st.subheader("Detailed Events for Each Replication")
        selected_replication = st.selectbox("Select Replication", options=list(individual_replications.keys()))
        st.write(f"**Details for Replication {selected_replication}:**")
        st.dataframe(individual_replications[selected_replication])

if __name__ == "__main__":
    main()
