import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

def main():
    # File paths
    file_paths = ["eda.csv", "eda_noise.csv"]
    output_dir = "cdup/reports"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    dfs = []
    for fp in file_paths:
        if os.path.exists(fp):
            dfs.append(pd.read_csv(fp))
        elif os.path.exists(os.path.join("cdup", fp)):
            dfs.append(pd.read_csv(os.path.join("cdup", fp)))
            
    if not dfs:
        print("Could not find eda.csv or eda_noise.csv.")
        return

    # Combine data
    df = pd.concat(dfs, ignore_index=True)

    if 'human_feedback' not in df.columns:
        print("Error: 'human_feedback' column not found in the CSV files. Did you run with the --human_feedback flag?")
        return

    # Filter for NOISE and TRUE only (exclude OTHER or empty)
    df = df[df['human_feedback'].isin(['NOISE', 'TRUE'])]

    if df.empty:
        print("Warning: No clones classified as NOISE or TRUE found in the datasets.")
        return

    # Set seaborn style
    sns.set_theme(style="whitegrid")

    # 1. Sequence Length by Classification
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='human_feedback', y='line_length')
    plt.title("Clone Sequence Length by Classification")
    plt.xlabel("Classification")
    plt.ylabel("Line Length")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_sequence_length.png"), dpi=300)
    plt.close()

    # 2. Entropy vs Total Words
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='total_words', y='entropy', hue='human_feedback', s=100, alpha=0.7)
    plt.title("Information Entropy vs. Total Words (TRUE vs NOISE)")
    plt.xlabel("Total Words")
    plt.ylabel("Entropy")
    plt.legend(title='Feedback')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_entropy_words.png"), dpi=300)
    plt.close()

    # 3. Type-Token Ratio (TTR)
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='human_feedback', y='ttr')
    plt.title("Type-Token Ratio (TTR) by Classification")
    plt.ylabel("TTR (Unique Words / Total Words)")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_ttr.png"), dpi=300)
    plt.close()

    # 4. Identifier Density
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='human_feedback', y='identifier_density')
    plt.title("Identifier Density by Classification")
    plt.ylabel("Identifier Density")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_id_density.png"), dpi=300)
    plt.close()

    # 5. Cyclomatic Complexity vs Total Words
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='total_words', y='cyclomatic_complexity', hue='human_feedback', s=100, alpha=0.7)
    plt.title("Cyclomatic Complexity vs. Total Words (TRUE vs NOISE)")
    plt.xlabel("Total Words")
    plt.ylabel("Cyclomatic Complexity Estimate")
    plt.legend(title='Feedback')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_complexity_words.png"), dpi=300)
    plt.close()

    # 6. Cross-File Spread
    plt.figure(figsize=(10, 6))
    sns.countplot(data=df, x='cross_file_spread', hue='human_feedback')
    plt.title("Cross-File Spread of Clones (TRUE vs NOISE)")
    plt.xlabel("Number of Unique Files")
    plt.ylabel("Count of Clone Classes")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_file_spread.png"), dpi=300)
    plt.close()

    # 7. Directory Spread
    plt.figure(figsize=(10, 6))
    sns.countplot(data=df, x='directory_spread', hue='human_feedback')
    plt.title("Directory Spread of Clones (TRUE vs NOISE)")
    plt.xlabel("Number of Unique Directories")
    plt.ylabel("Count of Clone Classes")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_dir_spread.png"), dpi=300)
    plt.close()

    print(f"Comparison plots successfully generated and saved to '{output_dir}/'")

if __name__ == "__main__":
    main()
