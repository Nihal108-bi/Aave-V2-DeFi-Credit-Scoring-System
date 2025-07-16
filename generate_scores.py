# -*- coding: utf-8 -*-
"""
Aave V2 Wallet Credit Scoring Script

This script takes a JSON file of Aave V2 transaction data, engineers features
to model wallet behavior, and assigns a credit score from 0 to 1000 to each wallet.

The final output is a CSV file containing the wallet address, its credit score,
and key features that determined the score.

Usage:
    python generate_scores.py --input user-wallet-transactions.json --output wallet_credit_scores.csv
"""

import json
import argparse
import logging
import pandas as pd
import numpy as np
from collections import defaultdict
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

# --- Configuration & Constants ---

# Configure logging to provide informative output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Features to be used for the K-Means clustering model
# These were selected to represent a wallet's risk, responsibility, and activity level.
MODEL_FEATURE_COLS = [
    'repay_borrow_ratio_count',
    'liquidation_ratio',
    'active_days',
    'total_usd_all_actions',
    'avg_time_between_tx_days'
]

# Number of clusters for K-Means. This determines the number of user archetypes.
N_CLUSTERS = 5

# --- Core Functions ---

def load_transaction_data(file_path: str) -> list:
    """
    Loads raw transaction data from a JSON file.

    Args:
        file_path: The path to the input JSON file.

    Returns:
        A list of transaction records.
    """
    logging.info(f"Loading raw transaction data from: {file_path}")
    try:
        with open(file_path, 'r') as f:
            raw_data = json.load(f)
        logging.info(f"Successfully loaded {len(raw_data)} records.")
        return raw_data
    except FileNotFoundError:
        logging.error(f"Error: Input file not found at {file_path}")
        return []
    except json.JSONDecodeError:
        logging.error(f"Error: Could not decode JSON from {file_path}. Please check the file format.")
        return []

def engineer_features(raw_data: list) -> pd.DataFrame:
    """
    Engineers a rich set of features from raw transaction data to model wallet behavior.

    Args:
        raw_data: A list of transaction records.

    Returns:
        A pandas DataFrame where each row represents a wallet and columns are engineered features.
    """
    if not raw_data:
        logging.warning("Input data is empty. Cannot engineer features.")
        return pd.DataFrame()

    logging.info("Starting feature engineering...")
    wallet_stats = defaultdict(lambda: defaultdict(float))
    wallet_timestamps = defaultdict(list)

    for tx in raw_data:
        wallet = tx.get('userWallet')
        action = tx.get('action', '').lower()
        timestamp = tx.get('timestamp')
        
        if not all([wallet, action, timestamp]):
            continue # Skip records with missing essential data

        try:
            # Normalize amount based on common token decimals (USDC uses 6)
            amount = float(tx['actionData']['amount']) / 1e6
            price = float(tx['actionData'].get('assetPriceUSD', 1.0))
            usd_value = amount * price
        except (ValueError, KeyError, TypeError):
            continue # Skip if amount/price data is invalid

        # Accumulate statistics for each wallet
        wallet_stats[wallet]['total_tx'] += 1
        wallet_stats[wallet]['total_usd_all_actions'] += usd_value
        wallet_stats[wallet][f'num_{action}'] += 1
        wallet_stats[wallet][f'total_usd_{action}'] += usd_value
        
        if 'actions_set' not in wallet_stats[wallet]: wallet_stats[wallet]['actions_set'] = set()
        wallet_stats[wallet]['actions_set'].add(action)
        
        wallet_timestamps[wallet].append(timestamp)

    # Find the latest timestamp in the dataset to calculate recency
    all_timestamps = [ts for times in wallet_timestamps.values() for ts in times]
    latest_timestamp = max(all_timestamps) if all_timestamps else 0

    features_list = []
    for wallet, stats in wallet_stats.items():
        total_tx = stats['total_tx']
        num_borrows = stats.get('num_borrow', 0)
        
        # Calculate behavioral and risk ratios
        repay_borrow_ratio_count = stats.get('num_repay', 0) / num_borrows if num_borrows > 0 else 1.0
        liquidation_ratio = stats.get('num_liquidationcall', 0) / total_tx if total_tx > 0 else 0
        
        # Calculate time-based features
        timestamps = sorted(wallet_timestamps.get(wallet, [0]))
        active_days = (timestamps[-1] - timestamps[0]) / 86400 if len(timestamps) > 1 else 0
        avg_time_between_tx_days = active_days / total_tx if total_tx > 1 else 0

        features_list.append({
            'wallet': wallet,
            'total_tx': total_tx,
            'total_usd_all_actions': stats['total_usd_all_actions'],
            'repay_borrow_ratio_count': repay_borrow_ratio_count,
            'num_liquidations': stats.get('num_liquidationcall', 0),
            'liquidation_ratio': liquidation_ratio,
            'active_days': active_days,
            'avg_time_between_tx_days': avg_time_between_tx_days,
        })

    df_features = pd.DataFrame(features_list).set_index('wallet')
    logging.info(f"Feature engineering complete. Created features for {len(df_features)} unique wallets.")
    return df_features

def generate_credit_scores(df_features: pd.DataFrame) -> pd.DataFrame:
    """
    Generates credit scores using K-Means clustering on the engineered features.

    Args:
        df_features: DataFrame of engineered features for each wallet.

    Returns:
        The input DataFrame with an added 'credit_score' column.
    """
    if df_features.empty:
        logging.warning("Feature DataFrame is empty. Skipping score generation.")
        return df_features

    logging.info("Generating credit scores using K-Means clustering...")
    
    # Prepare data for the model: select features, handle missing values, and scale
    X = df_features[MODEL_FEATURE_COLS].copy()
    X.replace([np.inf, -np.inf], 0, inplace=True)
    X.fillna(0, inplace=True)
    
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)

    # Train K-Means model
    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    df_features['cluster'] = kmeans.fit_predict(X_scaled)

    # Rank clusters based on a composite "good behavior" metric.
    # Higher repay ratio and lower liquidation ratio are considered better.
    cluster_health_metric = (df_features.groupby('cluster')['repay_borrow_ratio_count'].mean() - 
                             df_features.groupby('cluster')['liquidation_ratio'].mean() * 2) # Penalize liquidations heavily

    # Create a score mapping from the ranked clusters
    score_mapping = cluster_health_metric.rank(method='dense').astype(int) - 1
    
    # Assign the final credit score, scaling it from 0 to 1000
    df_features['credit_score'] = (df_features['cluster'].map(score_mapping) * (1000 / (N_CLUSTERS - 1))).astype(int)
    
    logging.info("Credit scores generated and assigned.")
    return df_features

def main():
    """
    Main function to orchestrate the credit scoring pipeline.
    """
    # Set up command-line argument parser
    parser = argparse.ArgumentParser(description="Aave V2 Wallet Credit Scoring Script")
    parser.add_argument('--input', type=str, required=True, help="Path to the input JSON transaction file.")
    parser.add_argument('--output', type=str, required=True, help="Path to save the output CSV file with credit scores.")
    args = parser.parse_args()

    # --- Pipeline Execution ---
    # 1. Load Data
    raw_data = load_transaction_data(args.input)
    
    if not raw_data:
        logging.info("Exiting script due to data loading issues.")
        return

    # 2. Engineer Features
    df_features = engineer_features(raw_data)
    
    if df_features.empty:
        logging.info("Exiting script as no features could be engineered.")
        return

    # 3. Generate Scores
    df_scored = generate_credit_scores(df_features)

    # 4. Save Final Output
    # Select key columns for the final report
    output_cols = [
        'total_tx',
        'total_usd_all_actions',
        'repay_borrow_ratio_count',
        'num_liquidations',
        'active_days',
        'credit_score'
    ]
    
    try:
        logging.info(f"Saving final scores to: {args.output}")
        df_scored[output_cols].to_csv(args.output, index_label='wallet')
        logging.info("Script finished successfully!")
    except Exception as e:
        logging.error(f"Failed to save output file. Error: {e}")

if __name__ == "__main__":
    main()
