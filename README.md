# Aave V2 Wallet Credit Scoring System

## 1. Overview

This project implements a data-driven pipeline to analyze on-chain transaction data from the Aave V2 protocol and assign a behavioral **credit score from 0 to 1000** to each wallet address. The primary objective is to quantify wallet reliability and risk based on historical interactions, such as deposits, borrows, repays, and liquidations.

A higher score signifies a user who is responsible and poses a lower risk to the protocol, while a lower score indicates potentially higher-risk or speculative behavior. The system uses an unsupervised machine learning approach to group wallets into distinct behavioral profiles and assign scores accordingly.

## 2. Methodology

The credit scoring engine is built on a two-stage process: comprehensive **Feature Engineering** to capture user behavior, followed by **Model-Based Scoring** using K-Means clustering to categorize and rank wallets.

### 2.1. Feature Engineering

To create a holistic view of each wallet's activity, we transform the raw transaction logs into a set of powerful, descriptive features. These features measure a wallet's activity level, financial health, risk profile, and overall engagement with the protocol.

| Feature Name               | Description                                                                                             | What It Measures         |
|----------------------------|---------------------------------------------------------------------------------------------------------|--------------------------|
| `total_tx`                 | Total number of transactions a wallet has performed.                                                    | Activity Level           |
| `total_usd_all_actions`    | Total USD value of all transactions (deposits, borrows, etc.).                                          | Economic Significance    |
| `active_days`              | Number of days between the wallet's first and last transaction.                                         | Longevity & Engagement   |
| `repay_borrow_ratio_count` | Ratio of `repay` actions to `borrow` actions. Set to `1.0` if there are no borrows.                     | Responsibility           |
| `repay_borrow_ratio_value` | Ratio of total USD repaid to total USD borrowed. Strong indicator of financial diligence.               | Financial Health         |
| `num_liquidations`         | Absolute count of times a wallet has been liquidated.                                                   | Risk Profile             |
| `liquidation_ratio`        | Ratio of liquidation events to the total number of transactions.                                        | Risk Profile             |
| `leverage_ratio`           | Ratio of total USD borrowed to total USD deposited (Loan-to-Value approximation).                       | Risk Appetite            |
| `avg_time_between_tx_days` | Average number of days between consecutive transactions.                                                | Activity Pattern         |
| `num_token_types`          | Number of unique crypto assets the wallet has interacted with.                                          | Portfolio Diversity      |
| `num_action_types`         | Number of unique actions (e.g., deposit, borrow) performed.                                             | Protocol Engagement      |


### 2.2. Scoring Model: K-Means Clustering

Since the dataset is unsupervised (lacking pre-defined "good" or "bad" labels), we use the **K-Means clustering** algorithm. This technique identifies distinct behavioral groups within the data without prior assumptions.

The scoring process is as follows:

1. **Data Preparation**: The engineered features are cleaned (handling NaNs and infinities) and then normalized using `MinMaxScaler` to ensure each feature contributes equally to the model.

2. **Clustering**: The scaled feature set is fed into a K-Means model, which partitions the wallets into **5 distinct clusters**. Each cluster represents a different user archetype (e.g., "Low-Risk Savers," "Active Traders," "High-Leverage Borrowers").

3. **Cluster Ranking**: The clusters are ranked based on a **"Cluster Health Metric"**, which is designed to prioritize responsible financial behavior. The metric is calculated as:

   > *Health Metric = (Average Repay/Borrow Ratio) - (Average Liquidation Ratio \* 2)*

   This formula rewards clusters with high repayment rates and heavily penalizes those with a history of liquidations.

4. **Score Assignment**: Based on the rank of the clusters, a final credit score is assigned in discrete tiers. The healthiest cluster receives a score of **1000**, the next receives **750**, and so on, down to **0** for the riskiest cluster. This creates five clear and interpretable credit brackets.

## 3. How to Run the Project

### Prerequisites

* Python 3.7+

* `pip` for package installation

### Setup & Execution

1. **Clone the Repository**

   ```bash
   git clone [https://github.com/your-username/aave-credit-scoring.git](https://github.com/Nihal108-bi/Aave-V2-DeFi-Credit-Scoring-System.git)
   cd aave-credit-scoring
Install Dependencies It is recommended to use a virtual environment. python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
pip install -r requirements.txt

Run the Scoring ScriptExecute the generate_scores.py script from your terminal, providing the path to the input JSON file and the desired output CSV file.python generate_scores.py --input data/user-wallet-transactions.json --output wallet_credit_scores.csv

The script will log its progress and create the wallet_credit_scores.csv file upon completion.
![File Structure](file_str.png)
Project Structure- The repository is organized as follows to ensure clarity and maintainability:

aave-credit-scoring/
│
├── data/
│   └── user-wallet-transactions.json   # Input transaction data (not included in repo)
│
├── notebooks/
│   └── feature_engineering.ipynb       # Exploratory Data Analysis (EDA) and model prototyping.
│
├── generate_scores.py                  # The main executable Python script for scoring.
├── requirements.txt                    # A list of required Python packages for setup.
├── README.md                           # This documentation file.
└── analysis.md                         # A detailed analysis of the scoring results and wallet behavior.

