import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

def main():
    # File paths
    tests_csv = "eda_tests.csv"
    low_quality_csv = "eda_low_quality.csv"
    output_dir = "cdup/reports"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Load data
    df_tests = pd.read_csv(tests_csv)
    df_tests['Source'] = 'Tests Directory'
    
    df_low_quality = pd.read_csv(low_quality_csv)
    df_low_quality['Source'] = 'Low Quality Programs'

    # Combine data
    df = pd.concat([df_tests, df_low_quality], ignore_index=True)

    # Convert generation to string (e.g. "G1", "G2") for better categorical plotting
    df['Generation_Str'] = 'GEN' + df['generation'].astype(str)
    
    # Set seaborn style
    sns.set_theme(style="whitegrid")

    # 1. Generation Counts by Source
    plt.figure(figsize=(10, 6))
    ax = sns.countplot(data=df, x='Generation_Str', hue='Source', order=sorted(df['Generation_Str'].unique()))
    plt.title("Number of Clone Classes per Generation")
    plt.xlabel("Generation")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_generation_counts.png"), dpi=300)
    plt.close()

    # 2. Sequence Length vs Generation
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='Generation_Str', y='line_length', hue='Source', order=sorted(df['Generation_Str'].unique()))
    plt.title("Clone Sequence Length by Generation")
    plt.xlabel("Generation")
    plt.ylabel("Line Length")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_generation_length.png"), dpi=300)
    plt.close()

    # 3. Entropy vs Total Words
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='total_words', y='entropy', hue='Source', style='Generation_Str', s=100, alpha=0.7)
    plt.title("Information Entropy vs. Total Words in Clone")
    plt.xlabel("Total Words")
    plt.ylabel("Entropy")
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_entropy_words.png"), dpi=300)
    plt.close()

    # 4. Type-Token Ratio (TTR)
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='Source', y='ttr')
    plt.title("Type-Token Ratio (TTR) by Source")
    plt.ylabel("TTR (Unique Words / Total Words)")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_ttr.png"), dpi=300)
    plt.close()

    # 5. Identifier Density
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='Source', y='identifier_density')
    plt.title("Identifier Density by Source")
    plt.ylabel("Identifier Density")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_id_density.png"), dpi=300)
    plt.close()

    # 6. Cyclomatic Complexity vs Total Words
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='total_words', y='cyclomatic_complexity', hue='Source', style='Generation_Str', s=100, alpha=0.7)
    plt.title("Cyclomatic Complexity vs. Total Words")
    plt.xlabel("Total Words")
    plt.ylabel("Cyclomatic Complexity Estimate")
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_complexity_words.png"), dpi=300)
    plt.close()

    # 7. Cross-File Spread
    plt.figure(figsize=(10, 6))
    sns.countplot(data=df, x='cross_file_spread', hue='Source')
    plt.title("Cross-File Spread of Clones")
    plt.xlabel("Number of Unique Files")
    plt.ylabel("Count of Clone Classes")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_file_spread.png"), dpi=300)
    plt.close()

    # 8. Directory Spread
    plt.figure(figsize=(10, 6))
    sns.countplot(data=df, x='directory_spread', hue='Source')
    plt.title("Directory Spread of Clones")
    plt.xlabel("Number of Unique Directories")
    plt.ylabel("Count of Clone Classes")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "comparison_dir_spread.png"), dpi=300)
    plt.close()

    print(f"Comparison plots successfully generated and saved to '{output_dir}/'")

if __name__ == "__main__":
    main()