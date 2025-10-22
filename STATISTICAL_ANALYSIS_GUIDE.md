# EthoGrid Statistical Analysis Module: A Detailed Guide

## Overview

The EthoGrid Statistical Analysis module is a powerful tool designed to take your raw endpoint data and transform it into publication-ready conclusions. It acts as a smart lab assistant, guiding you through best statistical practices to ensure your results are robust, reliable, and scientifically valid.

The core philosophy is **automation with user control**. The module automatically suggests and performs the correct statistical tests based on the properties of your data, but it always gives you, the researcher, the final say.

This guide explains each step of the process, from data grouping to the final plot, detailing the methods and formulas used.

---

## The Workflow: From Data to Decision

The module follows a standard, rigorous statistical workflow:

1.  **Data Grouping**: You assign your experimental data files (e.g., from different treatments) into named groups.
2.  **Normality Testing**: For each group, the module checks if the data follows a "bell curve" (a normal distribution). This is the most critical step.
3.  **Automated Test Selection**:
    *   If the data appears **normal**, the module selects a powerful **Parametric Test**.
    *   If the data is **not normal**, it selects a robust **Non-Parametric Test**.
4.  **Significance Calculation**: The chosen test is performed to calculate a **p-value**, which tells you if the differences between your groups are statistically significant.
5.  **Visualization**: A professional, publication-quality bar plot is generated to visually represent the results, complete with error bars and significance annotations.

---

## Step 1: Normality Testing - Is the Data "Bell-Shaped"?

> **For the Non-Technical User:**
> Imagine you measured the height of 1,000 people. Most would be around the average height, with fewer people being very short or very tall. This creates a "bell curve." Many powerful statistical tests (called parametric tests) work best when your data follows this pattern. The normality test is simply a way to ask: "Does my data look like a bell curve?"

The module offers two widely accepted tests to check for normality. The result is a **p-value**.

**The Decision Rule**: We use a significance level (alpha), typically set to **0.05**.
-   If `p-value >= 0.05`: We **cannot reject** the idea that the data is normal. It's "normal enough" to proceed with parametric tests.
-   If `p-value < 0.05`: We **reject** the idea of normality. The data is significantly different from a bell curve, and we should use safer, non-parametric tests.

#### Tests Implemented:

1.  **Shapiro-Wilk Test (Default)**
    -   **What it does**: Compares the sorted data points to what would be expected from a perfect bell curve. It's highly effective, especially for smaller sample sizes.
    -   **For the Analyst**: It calculates the *W* statistic, which would be 1.0 for perfectly normal data. The `scipy.stats.shapiro()` function is used to compute the *W* statistic and the corresponding p-value.

2.  **D'Agostino-Pearson K² Test**
    -   **What it does**: This test is excellent because it checks for two different ways data can deviate from a bell curve:
        -   **Skewness**: Is the curve lopsided to the left or right?
        -   **Kurtosis**: Is the curve too pointy or too flat?
    -   **For the Analyst**: It calculates a single K² statistic from the Z-scores of skewness (Z₁) and kurtosis (Z₂). The formula is:
        ```
        K² = Z₁² + Z₂²
        ```
        The `scipy.stats.normaltest()` function is used to compute the K² statistic and the p-value.

> **Edge Case Handling**: If all data points within a group are identical (e.g., all values are 0), the data has zero variance. In this case, a normality test cannot be run. The module will automatically classify this data as **NOT NORMAL** and proceed with non-parametric tests, which is the safest assumption.

---

## Step 2: Significance Testing - Are the Groups Different?

Based on the normality test and the number of groups you've created, the module automatically selects the appropriate test.

### Scenario A: Comparing Exactly Two Groups (e.g., Control vs. Treatment)

*   #### If Data is Normal (Parametric): **Independent T-test**
    *   **What it asks**: "Is the difference between the *means* (averages) of these two groups large enough to be considered real, or is it likely just due to random chance?"
    *   **For the Analyst**: The `scipy.stats.ttest_ind()` function is used. It calculates the t-statistic, conceptually:
        ```
        t = (mean₁ - mean₂) / √((s₁²/n₁) + (s₂²/n₂))
        ```
        Where `s` is the standard deviation and `n` is the sample size. A larger t-statistic leads to a smaller p-value.

*   #### If Data is Not Normal (Non-Parametric): **Mann-Whitney U Test**
    *   **What it asks**: "If we mix all the data points from both groups and rank them from smallest to largest, does one group consistently have higher ranks than the other?" It compares medians, not means, making it robust to outliers.
    *   **For the Analyst**: The `scipy.stats.mannwhitneyu()` function is used. It calculates the *U* statistic based on the sum of ranks for each group.

### Scenario B: Comparing More Than Two Groups (e.g., Control vs. T1 vs. T2)

*   #### If Data is Normal (Parametric): **One-Way ANOVA**
    *   **What it asks**: "Is there a significant difference *somewhere* among the means of all these groups?" It's an omnibus test that tells you if the groups are different overall, but not which specific pairs are different.
    *   **For the Analyst**: The `scipy.stats.f_oneway()` function is used. It calculates the F-statistic by comparing the variance *between* the groups to the variance *within* the groups.

*   #### If Data is Not Normal (Non-Parametric): **Kruskal-Wallis H Test**
    *   **What it asks**: "If you rank all data from all groups together, is the average rank for at least one group significantly different from the others?" It is the non-parametric equivalent of ANOVA.
    *   **For the Analyst**: The `scipy.stats.kruskal()` function is used.

> **User Override**: The **"Force Parametric Test"** checkbox allows you to bypass the normality check and use the parametric tests (T-test/ANOVA) even if the data was found to be non-normal. This should be used with caution and scientific justification.

---

## Step 3: Visualization - The Publication-Quality Plot

The final step is to create a clear and informative graph. The module generates a professional bar plot with several customizable components.

*   **Bar Height (`Mean` or `Median`)**: You can choose whether the height of each bar represents the **Mean** (the average value, best for normal data) or the **Median** (the middle value, best for non-normal or skewed data).

*   **Error Bars (`SD` or `SEM`)**: These lines show the variability in your data. This option is only active when "Mean" is selected.
    *   **Standard Deviation (SD)**: Shows how spread out the individual data points are from the mean of that group. Use this to describe the variance *within* your sample.
    *   **Standard Error of the Mean (SEM)**: Shows how precise your estimate of the group's true mean is. SEM bars are smaller than SD bars and are typically used to visually infer whether the difference between group means is significant.

*   **Individual Data Points**: To ensure full transparency (a best practice in modern science), the individual data points for each group are overlaid as a "strip plot." This allows you to see the distribution and identify any potential outliers.

*   **Significance Annotations**: If a comparison between two groups is found to be statistically significant (i.e., `p-value < alpha`), an annotation is automatically added above the bars:
    *   `*` for p < 0.05
    *   `**` for p < 0.01
    *   `***` for p < 0.001

*   **Full Customization**: You have complete control over the plot's appearance, including:
    *   Width, Height, and DPI for image resolution.
    *   Font sizes and weights for the title, axis labels, and tick labels.
    *   A selection of professional color palettes from `seaborn`.

By combining automated, statistically-sound test selection with full user control over the final visualization, the EthoGrid Statistical Analysis module aims to provide a reliable and efficient path from your data to your publication.
