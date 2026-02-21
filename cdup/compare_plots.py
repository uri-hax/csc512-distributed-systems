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

    # Convert generation to string (e.g. "G1", "G2") for better categorical plotting
    df['Generation_Str'] = 'GEN' + df['generation'].astype(str)
    
    # Set seaborn style
    sns.set_theme(style="whitegrid")

    # 1. Generation Counts by Feedback
    plt.figure(figsize=(10, 6))
    ax = sns.countplot(data=df, x='Generation_Str', hue='human_feedback', order=sorted(df['Generation_Str'].unique()))
    plt.title("Number of Clone Classes per Generation (TRUE vs NOISE)")
    plt.xlabel("Generation")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_generation_counts.png"), dpi=300)
    plt.close()

    # 2. Sequence Length vs Generation
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='Generation_Str', y='line_length', hue='human_feedback', order=sorted(df['Generation_Str'].unique()))
    plt.title("Clone Sequence Length by Generation (TRUE vs NOISE)")
    plt.xlabel("Generation")
    plt.ylabel("Line Length")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_generation_length.png"), dpi=300)
    plt.close()

    # 3. Entropy vs Total Words
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='total_words', y='entropy', hue='human_feedback', style='Generation_Str', s=100, alpha=0.7)
    plt.title("Information Entropy vs. Total Words (TRUE vs NOISE)")
    plt.xlabel("Total Words")
    plt.ylabel("Entropy")
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_entropy_words.png"), dpi=300)
    plt.close()

    # 4. Type-Token Ratio (TTR)
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='human_feedback', y='ttr')
    plt.title("Type-Token Ratio (TTR) by Classification")
    plt.ylabel("TTR (Unique Words / Total Words)")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_ttr.png"), dpi=300)
    plt.close()

    # 5. Identifier Density
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='human_feedback', y='identifier_density')
    plt.title("Identifier Density by Classification")
    plt.ylabel("Identifier Density")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_id_density.png"), dpi=300)
    plt.close()

    # 6. Cyclomatic Complexity vs Total Words
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='total_words', y='cyclomatic_complexity', hue='human_feedback', style='Generation_Str', s=100, alpha=0.7)
    plt.title("Cyclomatic Complexity vs. Total Words (TRUE vs NOISE)")
    plt.xlabel("Total Words")
    plt.ylabel("Cyclomatic Complexity Estimate")
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_complexity_words.png"), dpi=300)
    plt.close()

    # 7. Cross-File Spread
    plt.figure(figsize=(10, 6))
    sns.countplot(data=df, x='cross_file_spread', hue='human_feedback')
    plt.title("Cross-File Spread of Clones (TRUE vs NOISE)")
    plt.xlabel("Number of Unique Files")
    plt.ylabel("Count of Clone Classes")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_file_spread.png"), dpi=300)
    plt.close()

    # 8. Directory Spread
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
