import numpy as np
import pandas as pd

def entropy(y):
    counts = np.bincount(y)
    probabilities = counts / len(y)
    return -np.sum([p * np.log2(p) for p in probabilities if p > 0])

def information_gain(feature, y):
    total_entropy = entropy(y)
    values, counts = np.unique(feature, return_counts=True)
    
    weighted_entropy = sum((counts[i] / sum(counts)) * 
                           entropy(data[data[feature] == values[i]][target].values) 
                           for i in range(len(values)))
    return total_entropy - weighted_entropy

def gain_ratio(data, feature, target):
    ig = information_gain(data, feature, target)
    values, counts = np.unique(data[feature], return_counts=True)
    split_info = -np.sum((counts / sum(counts)) * np.log2(counts / sum(counts)))
    return ig / split_info if split_info != 0 else 0

def gini_index(data, feature, target):
    values, counts = np.unique(data[feature], return_counts=True)
    gini = 0
    for v in values:
        subset = data[data[feature] == v][target]
        subset_counts = np.bincount(subset)
        subset_prob = subset_counts / subset_counts.sum()
        gini += (counts[values == v] / sum(counts)) * (1 - np.sum(subset_prob ** 2))
    return gini