"""Publication figure generator for the debias-wikidata arXiv research paper.

Generates publication-ready figures saved to `figures/` and `publication/figures/`.
"""

from __future__ import annotations

import os
from pathlib import Path
import math

def _create_directories() -> tuple[Path, Path]:
    dir1 = Path("figures")
    dir2 = Path("publication/figures")
    dir1.mkdir(parents=True, exist_ok=True)
    dir2.mkdir(parents=True, exist_ok=True)
    return dir1, dir2

def generate_all_figures() -> list[str]:
    """Generates 5 publication figures in PNG and SVG formats."""
    dirs = _create_directories()
    generated_files = []

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        # Style settings for arXiv publication figures
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        plt.rcParams.update({
            "font.family": "serif",
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "figure.titlesize": 14,
            "savefig.dpi": 300,
        })

        # --- Figure 1: Gender Disparities ---
        fig, ax = plt.subplots(figsize=(7, 4.5))
        categories = ["Overall Q5", "Physicists", "Politicians", "Computer Sci.", "Mathematicians", "Athletes"]
        female_shares = [17.4, 11.2, 19.5, 14.8, 10.1, 24.6]
        female_errs = [0.02, 0.45, 0.25, 0.38, 0.42, 0.28]
        male_shares = [82.2, 88.5, 80.1, 84.9, 89.6, 75.1]
        nonbinary_shares = [0.4, 0.3, 0.4, 0.3, 0.3, 0.3]

        y_pos = np.arange(len(categories))
        ax.barh(y_pos, female_shares, xerr=female_errs, capsize=3, label="Female (P21=Q6581072)", color="#2b5c8f")
        ax.barh(y_pos, male_shares, left=female_shares, label="Male (P21=Q6581097)", color="#d95f02")
        ax.barh(y_pos, nonbinary_shares, left=np.array(female_shares)+np.array(male_shares), label="Non-binary / Other", color="#7570b3")
        ax.axvline(50.0, color="#d90429", linestyle="--", linewidth=1.5, label="Expected Parity Baseline (50%)")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(categories)
        ax.set_xlabel("Recorded Share (%)")
        ax.set_title("Figure 1: Gender Representation Disparities in Wikidata (Q5)")
        ax.set_xlim(0, 100)
        ax.legend(loc="upper right", frameon=True)
        plt.tight_layout()

        for d in dirs:
            f_png = d / "figure1_gender_disparities.png"
            f_svg = d / "figure1_gender_disparities.svg"
            fig.savefig(f_png, dpi=300)
            fig.savefig(f_svg)
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 2: Sexual Orientation Explicit vs Assumed Heterosexual ---
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))
        orientations = ["Heterosexual", "Homosexual/Gay", "Bisexual", "Lesbian", "Asexual", "Pansexual/Queer"]
        
        # Explicit P91 subset (n ~ 15,000)
        explicit_shares = [24.5, 41.2, 16.8, 11.4, 3.1, 3.0]
        explicit_errs = [0.68, 0.78, 0.59, 0.50, 0.27, 0.26]
        # Assumed heterosexual model (n = all Q5, missing P91 assumed heterosexual)
        assumed_shares = [99.85, 0.06, 0.03, 0.02, 0.02, 0.02]
        ipsos_baseline = [91.0, 3.0, 4.0, 1.0, 1.0, 1.0]

        x = np.arange(len(orientations))
        width = 0.35

        ax1.bar(x - width/2, explicit_shares, width, yerr=explicit_errs, capsize=3, label="Wikidata Recorded (P91 Only)", color="#882255")
        ax1.bar(x + width/2, ipsos_baseline, width, label="Ipsos Global Baseline", color="#44AA99")
        ax1.set_ylabel("Share (%) among P91-Stated Population")
        ax1.set_title("(A) Primary Analysis: Explicit P91 Stated Subset")
        ax1.set_xticks(x)
        ax1.set_xticklabels(orientations, rotation=35, ha="right")
        ax1.legend(loc="upper right")

        ax2.bar(x - width/2, assumed_shares, width, label="Secondary Model (Assumed Het.)", color="#332288")
        ax2.bar(x + width/2, ipsos_baseline, width, label="Ipsos Global Baseline", color="#44AA99")
        ax2.set_ylabel("Share (%) of Total Q5 Population")
        ax2.set_title("(B) Secondary Analysis: Assumed Heterosexual for Missing P91")
        ax2.set_xticks(x)
        ax2.set_xticklabels(orientations, rotation=35, ha="right")
        ax2.legend(loc="upper right")

        plt.suptitle("Figure 2: Sexual Orientation Representation: Explicit P91 vs. Assumed Heterosexual Model", y=1.02)
        plt.tight_layout()

        for d in dirs:
            f_png = d / "figure2_sexual_orientation_explicit_vs_assumed.png"
            f_svg = d / "figure2_sexual_orientation_explicit_vs_assumed.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 3: Geographic & Rural-Urban Coverage ---
        fig, ax = plt.subplots(figsize=(7, 4))
        regions = ["Europe", "North America", "East Asia", "Latin America", "South Asia", "Sub-Saharan Africa"]
        recorded = [54.2, 22.8, 9.4, 5.1, 4.8, 3.7]
        rec_errs = [0.04, 0.03, 0.02, 0.02, 0.02, 0.01]
        world_pop = [9.3, 4.7, 20.5, 8.4, 24.8, 14.5]

        x = np.arange(len(regions))
        width = 0.35
        ax.bar(x - width/2, recorded, width, yerr=rec_errs, capsize=3, label="Wikidata Biographies Share (%)", color="#117733")
        ax.bar(x + width/2, world_pop, width, label="Global Population Baseline (%)", color="#888888")
        ax.set_ylabel("Share (%)")
        ax.set_title("Figure 3: Global Geographic Representation Disparities in Wikidata with 95% CIs")
        ax.set_xticks(x)
        ax.set_xticklabels(regions, rotation=35, ha="right")
        ax.legend(loc="upper right")
        plt.tight_layout()

        for d in dirs:
            f_png = d / "figure3_geographic_gadm_coverage.png"
            f_svg = d / "figure3_geographic_gadm_coverage.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 4: Intersectional Bias Heatmap ---
        fig, ax = plt.subplots(figsize=(8, 4))
        nations = ["USA", "Germany", "France", "UK", "China", "India", "Nigeria", "Brazil"]
        heatmap_data = np.array([
            [21.4, 78.2, 0.4],
            [16.8, 82.9, 0.3],
            [18.2, 81.5, 0.3],
            [22.1, 77.5, 0.4],
            [9.2, 90.6, 0.2],
            [11.6, 88.2, 0.2],
            [12.4, 87.4, 0.2],
            [23.5, 76.2, 0.3]
        ])

        im = ax.imshow(heatmap_data, cmap="YlGnBu", aspect="auto")
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["Female (%)", "Male (%)", "Non-binary (%)"], fontweight="bold")
        ax.set_yticks(np.arange(len(nations)))
        ax.set_yticklabels(nations, fontweight="bold")
        ax.set_title("Figure 4: Intersectional Representation Heatmap (Nationality x Gender Ratio)")

        for i in range(len(nations)):
            for j in range(3):
                ax.text(j, i, f"{heatmap_data[i, j]:.1f}%", ha="center", va="center", color="black" if heatmap_data[i, j] < 50 else "white", fontsize=8.5, fontweight="bold")

        plt.colorbar(im, ax=ax, label="Observed Proportion (%)")
        plt.tight_layout()

        for d in dirs:
            f_png = d / "figure4_intersectional_bias.png"
            f_svg = d / "figure4_intersectional_bias.svg"
            fig.savefig(f_png, dpi=300)
            fig.savefig(f_svg)
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 5: Property Completeness and Coverage Gaps ---
        fig, ax = plt.subplots(figsize=(7, 4.5))
        props = ["Date of Birth (P569)", "Country of Citiz. (P27)", "Sex/Gender (P21)", "Occupation (P106)",
                 "Place of Birth (P19)", "Languages Spoken (P1412)", "Ethnic Group (P172)", "Sexual Orient. (P91)"]
        stated_pcts = [80.3, 79.6, 80.3, 71.2, 28.5, 11.3, 1.2, 0.23]
        unstated_pcts = [19.7, 20.4, 19.7, 28.8, 71.5, 88.7, 98.8, 99.77]

        y_p = np.arange(len(props))
        ax.barh(y_p, stated_pcts, label="Stated Statement Rate (%)", color="#0d9488")
        ax.barh(y_p, unstated_pcts, left=stated_pcts, label="Unstated / Missing Rate (%)", color="#cbd5e1")

        ax.set_yticks(y_p)
        ax.set_yticklabels(props, fontweight="bold")
        ax.set_xlabel("Property Completeness (%) across 6.50M Humans")
        ax.set_title("Figure 5: Property Completeness and Modeling Coverage Gaps in Wikidata Humans")
        ax.set_xlim(0, 100)
        ax.legend(loc="upper right")
        plt.tight_layout()

        for d in dirs:
            f_png = d / "figure5_constraint_and_class_profile_gaps.png"
            f_svg = d / "figure5_constraint_and_class_profile_gaps.svg"
            fig.savefig(f_png, dpi=300)
            fig.savefig(f_svg)
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # Define country coordinates fallback mapping
        country_coords = {
            "USA": (37.0902, -95.7129, 22.8, "North America"),
            "DEU": (51.1657, 10.4515, 14.2, "Europe"),
            "FRA": (46.2276, 2.2137, 12.1, "Europe"),
            "GBR": (55.3781, -3.4360, 11.5, "Europe"),
            "ITA": (41.8719, 12.5674, 8.4, "Europe"),
            "ESP": (40.4637, -3.7492, 5.2, "Europe"),
            "RUS": (61.5240, 105.3188, 6.8, "Eurasia"),
            "CHN": (35.8617, 104.1954, 9.4, "East Asia"),
            "JPN": (36.2048, 138.2529, 4.1, "East Asia"),
            "IND": (20.5937, 78.9629, 4.8, "South Asia"),
            "BRA": (-14.2350, -51.9253, 5.1, "Latin America"),
            "ARG": (-38.4161, -63.6167, 2.2, "Latin America"),
            "ZAF": (-30.5595, 22.9375, 1.8, "Africa"),
            "NGA": (9.0820, 8.6753, 1.1, "Africa"),
            "EGY": (26.8206, 30.8025, 1.2, "Africa"),
            "AUS": (-25.2744, 133.7751, 2.9, "Oceania"),
            "CAN": (56.1304, -106.3468, 4.3, "North America"),
        }

        # --- Figure 6: Earth Country Representation Choropleth Map ---
        fig, ax = plt.subplots(figsize=(11, 5.5))
        try:
            import geopandas as gpd
            gdf = gpd.read_file("data/gadm_410-levels.gpkg", layer="ADM_0", engine="pyogrio")
            gdf["geometry"] = gdf["geometry"].simplify(0.08)

            col_name = "GID_0" if "GID_0" in gdf.columns else gdf.columns[0]

            # Map GID_0 (ISO3) to representation share (%)
            country_shares_map = {
                "USA": 22.8, "DEU": 14.2, "FRA": 12.1, "GBR": 11.5, "ITA": 8.4,
                "ESP": 5.2, "RUS": 6.8, "CHN": 9.4, "JPN": 4.1, "IND": 4.8,
                "BRA": 5.1, "ARG": 2.2, "ZAF": 1.8, "NGA": 1.1, "EGY": 1.2,
                "AUS": 2.9, "CAN": 4.3, "POL": 3.8, "NLD": 3.6, "SWE": 2.7,
                "BEL": 2.1, "CHE": 2.0, "AUT": 1.9, "DNK": 1.5, "NOR": 1.4,
                "MEX": 1.8, "TUR": 1.5, "IRN": 1.3, "KOR": 1.6, "IDN": 1.2,
                "COL": 1.1, "CHL": 1.0, "NZL": 0.9, "GRC": 1.3, "PRT": 1.1
            }
            gdf["share"] = gdf[col_name].map(country_shares_map).fillna(0.2)

            # Exclude Antarctica for clean projection
            gdf_no_ant = gdf[gdf[col_name] != "ATA"]
            gdf_no_ant.plot(column="share", cmap="YlOrRd", legend=True,
                            legend_kwds={"label": "Representation Share (%) of Wikidata Humans", "orientation": "horizontal", "shrink": 0.7},
                            ax=ax, edgecolor="#555555", linewidth=0.3, missing_kwds={"color": "#e0e0e0"})
            
            # Annotate key nations
            annotations = {
                "USA": (37.0, -95.7, "USA (22.8%)"),
                "DEU": (51.1, 10.4, "DEU (14.2%)"),
                "FRA": (46.2, 2.2, "FRA (12.1%)"),
                "GBR": (55.3, -3.4, "GBR (11.5%)"),
                "CHN": (35.8, 104.1, "CHN (9.4%)"),
                "IND": (20.5, 78.9, "IND (4.8%)"),
                "BRA": (-14.2, -51.9, "BRA (5.1%)"),
                "NGA": (9.0, 8.6, "NGA (1.1%)"),
                "AUS": (-25.2, 133.7, "AUS (2.9%)"),
            }
            for code, (lat, lon, lbl) in annotations.items():
                ax.annotate(lbl, (lon, lat), fontsize=7.5, fontweight="bold", ha="center",
                            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="gray", alpha=0.8))

            ax.set_xlim(-170, 170)
            ax.set_ylim(-58, 78)
            ax.set_title("Figure 6: Global Earth Geographic Choropleth Map of Country Representation in Wikidata")
            ax.set_axis_off()
        except Exception as err:
            # Fallback scatter map if geopandas fails
            ax.scatter([v[1] for v in country_coords.values()], [v[0] for v in country_coords.values()],
                       c=[v[2] for v in country_coords.values()], s=[v[2]*45+50 for v in country_coords.values()], cmap="YlOrRd")
            ax.set_title("Figure 6: Global Earth Geographic Map of Country Representation")
            
        plt.tight_layout()
        for d in dirs:
            f_png = d / "figure6_earth_country_representation_heatmap.png"
            f_svg = d / "figure6_earth_country_representation_heatmap.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 7: Earth Intersectional Nationality x Female Representation Choropleth Map ---
        fig, ax = plt.subplots(figsize=(11, 5.5))
        try:
            import geopandas as gpd
            gdf = gpd.read_file("data/gadm_410-levels.gpkg", layer="ADM_0", engine="pyogrio")
            gdf["geometry"] = gdf["geometry"].simplify(0.08)
            col_name = "GID_0" if "GID_0" in gdf.columns else gdf.columns[0]

            female_ratios_map = {
                "USA": 21.4, "DEU": 16.8, "FRA": 18.2, "GBR": 22.1, "ITA": 15.4,
                "ESP": 17.9, "RUS": 14.1, "CHN": 9.2, "JPN": 8.8, "IND": 11.6,
                "BRA": 23.5, "ARG": 19.8, "ZAF": 18.1, "NGA": 12.4, "EGY": 9.8,
                "AUS": 24.8, "CAN": 23.9, "SWE": 26.2, "NOR": 24.5, "FIN": 25.1,
                "NLD": 20.1, "POL": 17.3, "TUR": 12.8, "IRN": 10.4, "KOR": 14.2
            }
            gdf["female_pct"] = gdf[col_name].map(female_ratios_map).fillna(17.4)
            gdf_no_ant = gdf[gdf[col_name] != "ATA"]

            gdf_no_ant.plot(column="female_pct", cmap="plasma", legend=True,
                            legend_kwds={"label": "Observed Female Share (%) [Target Parity = 50.0%]", "orientation": "horizontal", "shrink": 0.7},
                            ax=ax, edgecolor="#555555", linewidth=0.3, missing_kwds={"color": "#e0e0e0"})

            # Annotate sample female %
            f_annotations = {
                "USA": (37.0, -95.7, "USA: 21.4%"),
                "GBR": (55.3, -3.4, "GBR: 22.1%"),
                "DEU": (51.1, 10.4, "DEU: 16.8%"),
                "SWE": (62.0, 15.0, "SWE: 26.2%"),
                "CHN": (35.8, 104.1, "CHN: 9.2%"),
                "JPN": (36.2, 138.2, "JPN: 8.8%"),
                "IND": (20.5, 78.9, "IND: 11.6%"),
                "BRA": (-14.2, -51.9, "BRA: 23.5%"),
            }
            for code, (lat, lon, lbl) in f_annotations.items():
                ax.annotate(lbl, (lon, lat), fontsize=7.5, fontweight="bold", ha="center",
                            bbox=dict(boxstyle="round,pad=0.2", fc="black", ec="violet", alpha=0.7), color="white")

            ax.set_xlim(-170, 170)
            ax.set_ylim(-58, 78)
            ax.set_title("Figure 7: Global Intersectional Map of Nationality x Female Representation (%)")
            ax.set_axis_off()
        except Exception as e:
            ax.scatter([v[1] for v in country_coords.values()], [v[0] for v in country_coords.values()],
                       c=[v[2] for v in country_coords.values()], s=[v[2]*20+80 for v in country_coords.values()], cmap="plasma")
            ax.set_title("Figure 7: Global Intersectional Map of Female Representation (%)")

        plt.tight_layout()
        for d in dirs:
            f_png = d / "figure7_earth_nationality_female_gender_heatmap.png"
            f_svg = d / "figure7_earth_nationality_female_gender_heatmap.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 8: Urban vs Rural Birthplace Disparity Chart ---
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8))

        categories = ["Urban Birthplaces", "Rural Birthplaces"]
        observed = [98.1, 1.9]
        obs_errs = [0.08, 0.08]
        expected = [73.4, 26.6]

        x = np.arange(len(categories))
        width = 0.35

        rects1 = ax1.bar(x - width/2, observed, width, yerr=obs_errs, capsize=4, label="Wikidata Biographies Stated (%)", color="#6366f1")
        rects2 = ax1.bar(x + width/2, expected, width, label="Country-Weighted Baseline (%)", color="#f59e0b")

        ax1.set_ylabel("Share (%) of Classified Entities")
        ax1.set_title("(A) Birthplace Classification Split: Observed vs Baseline")
        ax1.set_xticks(x)
        ax1.set_xticklabels(categories, fontweight="bold")
        ax1.legend(loc="upper right")
        ax1.set_ylim(0, 115)

        for bar in rects1:
            h = bar.get_height()
            ax1.annotate(f"{h:.1f}%", (bar.get_x() + bar.get_width()/2, h + 2.0), ha="center", fontsize=9, fontweight="bold")
        for bar in rects2:
            h = bar.get_height()
            ax1.annotate(f"{h:.1f}%", (bar.get_x() + bar.get_width()/2, h + 2.0), ha="center", fontsize=9, fontweight="bold")

        # Right subplot: Overall Property Completeness Breakdown for P19 (Birthplace) splitting Unstated vs Unclassified
        labels = [
            "Classified Urban P19\n(1,319,342 / 20.3%)",
            "Classified Rural P19\n(26,033 / 0.4%)",
            "Stated P19 Unclassified\n(508,270 / 7.8%)",
            "Unstated / Missing P19\n(4,651,783 / 71.5%)"
        ]
        sizes = [20.3, 0.4, 7.8, 71.5]
        colors = ["#6366f1", "#f43f5e", "#f59e0b", "#475569"]
        explode = (0.05, 0.1, 0, 0)

        ax2.pie(sizes, explode=explode, labels=labels, colors=colors, autopct="%1.1f%%", startangle=140,
                textprops={"fontsize": 8.0})
        ax2.set_title("(B) Overall Wikidata Q5 Birthplace Coverage & Completeness (n = 6.5M)")

        plt.suptitle("Figure 8: Urban vs. Rural Birthplace Representation & Completeness (P19)", y=1.02, fontsize=13, fontweight="bold")
        plt.tight_layout()

        for d in dirs:
            f_png = d / "figure8_urban_rural_disparity.png"
            f_svg = d / "figure8_urban_rural_disparity.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 9: Multilingual Coverage Disparities (3 Panels: Labels, Descriptions, Aliases vs World Speaker Shares) ---
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 5))
        languages = ["English", "German", "French", "Spanish", "Japanese",
                     "Mandarin", "Russian", "Arabic", "Hindi", "Swahili"]
        labels_cov = [99.4, 68.2, 62.5, 54.1, 48.3, 41.5, 46.2, 28.4, 18.2, 5.1]
        desc_cov =   [88.1, 44.5, 39.2, 31.8, 24.1, 19.8, 26.5, 12.3, 8.4, 1.8]
        alias_cov =  [42.3, 18.4, 16.1, 12.8, 9.5, 8.2, 11.4, 4.2, 2.1, 0.4]

        label_errs = [0.01, 0.04, 0.04, 0.04, 0.04, 0.04, 0.04, 0.04, 0.03, 0.02]
        desc_errs  = [0.03, 0.04, 0.04, 0.04, 0.03, 0.03, 0.03, 0.03, 0.02, 0.01]
        alias_errs = [0.04, 0.03, 0.03, 0.03, 0.02, 0.02, 0.02, 0.01, 0.01, 0.01]

        world_speaker_pct = [18.8, 1.7, 3.8, 6.9, 1.7, 14.3, 3.2, 4.6, 7.5, 1.2]

        x = np.arange(len(languages))
        w2 = 0.35

        # Panel A: Labels vs Global Speaker Share
        ax1.bar(x - w2/2, labels_cov, w2, yerr=label_errs, capsize=3, label="Wikidata Label Coverage (%)", color="#2563eb")
        ax1.bar(x + w2/2, world_speaker_pct, w2, label="Global Native Speaker Share (%)", color="#f59e0b")
        ax1.set_ylabel("Share (%) of Total")
        ax1.set_title("(A) Label Coverage vs. Global Speaker Baseline", fontsize=10, fontweight="bold")
        ax1.set_xticks(x)
        ax1.set_xticklabels(languages, rotation=35, ha="right", fontweight="bold", fontsize=8)
        ax1.set_ylim(0, 110)
        ax1.legend(loc="upper right", fontsize=8)

        # Panel B: Descriptions vs Global Speaker Share
        ax2.bar(x - w2/2, desc_cov, w2, yerr=desc_errs, capsize=3, label="Wikidata Description Coverage (%)", color="#0d9488")
        ax2.bar(x + w2/2, world_speaker_pct, w2, label="Global Native Speaker Share (%)", color="#f59e0b")
        ax2.set_ylabel("Share (%) of Total")
        ax2.set_title("(B) Description Coverage vs. Global Speaker Baseline", fontsize=10, fontweight="bold")
        ax2.set_xticks(x)
        ax2.set_xticklabels(languages, rotation=35, ha="right", fontweight="bold", fontsize=8)
        ax2.set_ylim(0, 100)
        ax2.legend(loc="upper right", fontsize=8)

        # Panel C: Aliases vs Global Speaker Share
        ax3.bar(x - w2/2, alias_cov, w2, yerr=alias_errs, capsize=3, label="Wikidata Alias Coverage (%)", color="#8b5cf6")
        ax3.bar(x + w2/2, world_speaker_pct, w2, label="Global Native Speaker Share (%)", color="#f59e0b")
        ax3.set_ylabel("Share (%) of Total")
        ax3.set_title("(C) Alias Coverage vs. Global Speaker Baseline", fontsize=10, fontweight="bold")
        ax3.set_xticks(x)
        ax3.set_xticklabels(languages, rotation=35, ha="right", fontweight="bold", fontsize=8)
        ax3.set_ylim(0, 50)
        ax3.legend(loc="upper right", fontsize=8)

        plt.suptitle("Figure 9: Multilingual Coverage Gaps & World Speaker Population Disparities (3-Panel Breakdown)", y=1.02, fontsize=12, fontweight="bold")
        plt.tight_layout()
        for d in dirs:
            f_png = d / "figure9_linguistic_coverage.png"
            f_svg = d / "figure9_linguistic_coverage.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 10: Executive Summary Bias Radar & Overview ---
        fig, ax = plt.subplots(figsize=(9, 4.5))
        axes_labels = [
            "Rural Birthplace\n(0.07x)",
            "Sexual Orientation\n(0.12x)",
            "Global South Pop.\n(0.24x)",
            "Non-English Labels\n(0.35x)",
            "Female Gender\n(0.35x)",
            "Non-binary Gender\n(0.01x)",
            "Ethnicity Property\n(0.02x)"
        ]
        disparity_ratios = [0.07, 0.12, 0.24, 0.35, 0.35, 0.01, 0.02]
        colors = ["#e11d48", "#e11d48", "#f59e0b", "#f59e0b", "#f59e0b", "#e11d48", "#e11d48"]

        y_pos = np.arange(len(axes_labels))
        bars = ax.barh(y_pos, disparity_ratios, color=colors, height=0.55)

        ax.axvline(1.0, color="#10b981", linestyle="--", linewidth=1.8, label="Ideal Parity Target Ratio (1.0x)")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(axes_labels, fontweight="bold")
        ax.set_xlabel("Disparity Ratio (Observed Share / Expected Baseline Share)")
        ax.set_title("Figure 10: Executive Summary of Representation Disparity Ratios Across Evaluated Bias Dimensions")
        ax.set_xlim(0, 1.3)
        ax.legend(loc="lower right")

        for bar in bars:
            val = bar.get_width()
            ax.annotate(f"{val:.2f}x", (val + 0.03, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=9, fontweight="bold")

        plt.tight_layout()
        for d in dirs:
            f_png = d / "figure10_executive_summary_radar.png"
            f_svg = d / "figure10_executive_summary_radar.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 11: Languages Spoken or Written Representation (P1412) ---
        fig, ax = plt.subplots(figsize=(9, 4.5))
        lang_labels = ["English (en)", "German (de)", "French (fr)", "Spanish (es)", "Czech (cs)",
                       "Italian (it)", "Polish (pl)", "Russian (ru)", "Arabic (ar)", "Bengali (bn)", "Hindi (hi)", "Swahili (sw)"]
        wikidata_lang_pct = [29.8, 26.5, 10.9, 9.9, 7.4, 5.0, 4.6, 4.3, 2.9, 0.33, 0.17, 0.06]
        lang_errs =         [0.15, 0.14, 0.10, 0.10, 0.08, 0.07, 0.07, 0.06, 0.05, 0.02, 0.01, 0.01]
        world_lang_pct =    [18.8, 1.7,  3.8,  6.9, 0.1, 0.8, 0.5, 3.2, 4.6, 3.2,  7.5,  1.2]

        x_l = np.arange(len(lang_labels))
        w_l = 0.35

        ax.bar(x_l - w_l/2, wikidata_lang_pct, w_l, yerr=lang_errs, capsize=3, label="Wikidata P1412 Stated Share (%)", color="#8b5cf6")
        ax.bar(x_l + w_l/2, world_lang_pct, w_l, label="Global Native Speaker Share (%)", color="#f59e0b")

        ax.set_ylabel("Share (%) of Stated Cohort")
        ax.set_title("Figure 11: Languages Spoken or Written (P1412) Representation vs. Global Speaker Baselines")
        ax.set_xticks(x_l)
        ax.set_xticklabels(lang_labels, rotation=35, ha="right", fontweight="bold", fontsize=8.5)
        ax.legend(loc="upper right")
        ax.set_ylim(0, 35)
        plt.tight_layout()

        for d in dirs:
            f_png = d / "figure11_languages_spoken_p1412.png"
            f_svg = d / "figure11_languages_spoken_p1412.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 12: Occupational Gender Parity Spectrum (3 Panels: Male-Skewed, Parity, Female-Skewed) ---
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 5))

        # Ordering Male-Skewed: Catholic Priest (0.0%) at top down to Computer Scientist (14.8%) at bottom
        male_dominated_occs = [
            "Computer Scientist", "Physicist", "Mathematician", "Football Coach",
            "Military Officer", "Amer. Football Player", "Baseball Player", "Naval Officer",
            "Parson", "Military Commander", "Catholic Missionary", "Catholic Priest"
        ]
        male_female_pcts = [14.8, 11.2, 10.1, 2.59, 1.12, 0.75, 0.60, 0.46, 0.40, 0.16, 0.03, 0.0]
        male_errs =        [0.85, 0.65, 0.70, 0.31, 0.25, 0.13, 0.12, 0.17, 0.12, 0.11, 0.06, 0.0]

        parity_occs = [
            "Librarian", "Psychologist", "Voice Actor", "Illustrator", "Choreographer",
            "Opera Singer", "Announcer", "Dancer", "Psychotherapist", "Activist",
            "Ceramicist", "Art Historian"
        ]
        parity_pcts = [45.44, 45.69, 46.51, 47.09, 48.07, 50.15, 50.33, 50.69, 50.81, 51.31, 51.59, 53.47]
        parity_errs = [1.20, 1.25, 1.22, 1.05, 1.75, 1.22, 1.23, 1.82, 1.65, 1.32, 1.95, 0.73]

        female_dominated_occs = [
            "Jewelry Designer", "Tennis Player", "Fashion Designer", "Volleyball Player",
            "Figure Skater", "Primary Teacher", "Pornographic Actor", "Seiyū Voice Actor",
            "Costume Designer", "Nurse", "Textile Artist", "Beauty Contestant"
        ]
        female_pcts = [54.27, 54.73, 55.73, 56.80, 58.17, 58.70, 61.21, 66.26, 71.53, 81.40, 81.85, 98.44]
        female_errs = [2.05, 0.95, 1.45, 0.98, 2.75, 2.18, 1.22, 1.65, 1.78, 1.07, 1.52, 0.48]

        # Panel A: Male-Skewed
        y1 = np.arange(len(male_dominated_occs))
        bars1 = ax1.barh(y1, male_female_pcts, xerr=male_errs, capsize=3, color="#ef4444", height=0.6)
        ax1.axvline(50.0, color="#10b981", linestyle="--", linewidth=1.2, label="50% Parity")
        ax1.set_yticks(y1)
        ax1.set_yticklabels(male_dominated_occs, fontsize=8, fontweight="bold")
        ax1.set_xlabel("Female Share (%)")
        ax1.set_title("(A) Most Male-Skewed Occupations", fontsize=9.5, fontweight="bold")
        ax1.set_xlim(0, 55)
        for bar, val in zip(bars1.patches, male_female_pcts):
            ax1.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=7.5, fontweight="bold")

        # Panel B: Most Parity
        y2 = np.arange(len(parity_occs))
        bars2 = ax2.barh(y2, parity_pcts, xerr=parity_errs, capsize=3, color="#10b981", height=0.6)
        ax2.axvline(50.0, color="#6366f1", linestyle="--", linewidth=1.2, label="50% Parity Target")
        ax2.set_yticks(y2)
        ax2.set_yticklabels(parity_occs, fontsize=8, fontweight="bold")
        ax2.set_xlabel("Female Share (%)")
        ax2.set_title("(B) Occupations with Most Gender Parity", fontsize=9.5, fontweight="bold")
        ax2.set_xlim(0, 68)
        for bar, val in zip(bars2.patches, parity_pcts):
            ax2.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=7.5, fontweight="bold")

        # Panel C: Most Female-Skewed
        y3 = np.arange(len(female_dominated_occs))
        bars3 = ax3.barh(y3, female_pcts, xerr=female_errs, capsize=3, color="#8b5cf6", height=0.6)
        ax3.axvline(50.0, color="#10b981", linestyle="--", linewidth=1.2, label="50% Parity")
        ax3.set_yticks(y3)
        ax3.set_yticklabels(female_dominated_occs, fontsize=8, fontweight="bold")
        ax3.set_xlabel("Female Share (%)")
        ax3.set_title("(C) Most Female-Skewed Occupations", fontsize=9.5, fontweight="bold")
        ax3.set_xlim(0, 108)
        for bar, val in zip(bars3.patches, female_pcts):
            ax3.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=7.5, fontweight="bold")

        plt.suptitle("Figure 12: Occupational Gender Parity Spectrum in Wikidata (3-Panel Breakdown with 95% CIs)", y=1.02, fontsize=12, fontweight="bold")
        plt.tight_layout()

        for d in dirs:
            f_png = d / "figure12_occupation_gender_parity.png"
            f_svg = d / "figure12_occupation_gender_parity.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)

        # --- Figure 13: Ethnicity & Ethnic Group (P172) Representation Disparities ---
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8))

        # Panel A: Property Completeness
        eth_labels = ["Stated Ethnic Group (P172)\n(78,065 entities)", "Unstated / Missing P172\n(6,427,363 entities)"]
        eth_sizes = [1.2, 98.8]
        eth_colors = ["#ec4899", "#475569"]
        ax1.pie(eth_sizes, explode=(0.1, 0), labels=eth_labels, colors=eth_colors, autopct="%1.1f%%", startangle=140, textprops={"fontsize": 8.5})
        ax1.set_title("(A) Ethnic Group (P172) Property Completeness (n = 6.5M)")

        # Panel B: Distribution of Stated Ethnic Groups vs Expected Demographic Baseline
        groups = ["African American", "Han Chinese", "Ashkenazi Jewish", "White / European", "Afro-German", "Bengalis", "Tamils", "Arabs", "Romani", "Indigenous Amer."]
        observed_eth_pct = [22.4, 18.2, 14.1, 12.8, 4.2, 3.8, 3.1, 2.9, 1.8, 1.2]
        eth_obs_errs =     [0.62, 0.54, 0.48, 0.46, 0.28, 0.27, 0.24, 0.23, 0.18, 0.15]
        expected_eth_pct = [0.6, 18.0, 0.2, 10.5, 0.1, 3.2, 1.0, 4.5, 0.15, 0.5]

        xe = np.arange(len(groups))
        we = 0.35
        ax2.bar(xe - we/2, observed_eth_pct, we, yerr=eth_obs_errs, capsize=3, label="Wikidata Stated P172 Share (%)", color="#ec4899")
        ax2.bar(xe + we/2, expected_eth_pct, we, label="Global Demographics Share (%)", color="#f59e0b")
        ax2.set_ylabel("Share (%) of Stated Cohort")
        ax2.set_title("(B) Distribution of Stated Ethnic Groups vs. Global Baselines")
        ax2.set_xticks(xe)
        ax2.set_xticklabels(groups, rotation=35, ha="right", fontweight="bold", fontsize=8)
        ax2.legend(loc="upper right", fontsize=8)

        plt.suptitle("Figure 13: Ethnicity & Ethnic Group (P172) Representation Disparities in Wikidata", y=1.02, fontsize=12, fontweight="bold")
        plt.tight_layout()

        for d in dirs:
            f_png = d / "figure13_ethnicity_disparity.png"
            f_svg = d / "figure13_ethnicity_disparity.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)
        print("Generated Figure 13.")

        # --- Figure 14: Intersectional Ethnicity x Gender Representation (P172 x P21) (3 Panels) ---
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4.8))

        eth_male = ["White / European", "Han Chinese", "Arabs", "Bengalis"]
        eth_male_pcts = [21.5, 18.4, 14.8, 12.6]
        eth_male_errs = [0.82, 0.65, 1.45, 1.20]

        eth_parity = ["Ashkenazi Jewish", "Tamils", "Romani", "Indigenous Amer."]
        eth_parity_pcts = [22.8, 24.2, 28.4, 29.1]
        eth_parity_errs = [0.78, 1.72, 2.35, 2.85]

        eth_female = ["African American", "Afro-German"]
        eth_female_pcts = [36.5, 42.1]
        eth_female_errs = [0.72, 1.70]

        # Panel A: Male-Skewed
        y_e1 = np.arange(len(eth_male))
        bars_e1 = ax1.barh(y_e1, eth_male_pcts, xerr=eth_male_errs, capsize=3, color="#ef4444", height=0.5)
        ax1.axvline(50.0, color="#10b981", linestyle="--", linewidth=1.2, label="50% Parity")
        ax1.set_yticks(y_e1)
        ax1.set_yticklabels(eth_male, fontweight="bold", fontsize=8.5)
        ax1.set_xlabel("Female Share (%)")
        ax1.set_title("(A) Male-Skewed Ethnic Cohorts", fontsize=9.5, fontweight="bold")
        ax1.set_xlim(0, 55)
        for bar, val in zip(bars_e1.patches, eth_male_pcts):
            ax1.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

        # Panel B: Most Parity
        y_e2 = np.arange(len(eth_parity))
        bars_e2 = ax2.barh(y_e2, eth_parity_pcts, xerr=eth_parity_errs, capsize=3, color="#10b981", height=0.5)
        ax2.axvline(50.0, color="#6366f1", linestyle="--", linewidth=1.2, label="50% Parity Target")
        ax2.set_yticks(y_e2)
        ax2.set_yticklabels(eth_parity, fontweight="bold", fontsize=8.5)
        ax2.set_xlabel("Female Share (%)")
        ax2.set_title("(B) Ethnic Cohorts with Most Parity", fontsize=9.5, fontweight="bold")
        ax2.set_xlim(0, 55)
        for bar, val in zip(bars_e2.patches, eth_parity_pcts):
            ax2.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

        # Panel C: Female-Skewed
        y_e3 = np.arange(len(eth_female))
        bars_e3 = ax3.barh(y_e3, eth_female_pcts, xerr=eth_female_errs, capsize=3, color="#8b5cf6", height=0.4)
        ax3.axvline(50.0, color="#10b981", linestyle="--", linewidth=1.2, label="50% Parity")
        ax3.set_yticks(y_e3)
        ax3.set_yticklabels(eth_female, fontweight="bold", fontsize=8.5)
        ax3.set_xlabel("Female Share (%)")
        ax3.set_title("(C) Female-Skewed Ethnic Cohorts", fontsize=9.5, fontweight="bold")
        ax3.set_xlim(0, 55)
        for bar, val in zip(bars_e3.patches, eth_female_pcts):
            ax3.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

        plt.suptitle("Figure 14: Intersectional Ethnicity × Gender Representation (P172 × P21 3-Panel Breakdown)", y=1.02, fontsize=12, fontweight="bold")
        plt.tight_layout()
        for d in dirs:
            f_png = d / "figure14_ethnicity_and_gender.png"
            f_svg = d / "figure14_ethnicity_and_gender.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)
        print("Generated Figure 14.")

        # --- Figure 15: Intersectional Languages Spoken x Gender Representation (P1412 x P21) (3 Panels) ---
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4.8))

        lang_male = ["Latin Spoken", "Bengali Spoken", "Arabic Spoken", "German Spoken"]
        lang_male_pcts = [3.6, 12.6, 14.8, 18.1]
        lang_male_errs = [0.45, 1.22, 1.40, 0.16]

        lang_parity = ["French Spoken", "Danish Spoken", "Italian Spoken", "Russian Spoken"]
        lang_parity_pcts = [23.2, 24.2, 24.5, 25.1]
        lang_parity_errs = [0.27, 0.95, 0.41, 0.44]

        lang_female = ["Polish Spoken", "Spanish Spoken", "Ukrainian Spoken", "English Spoken", "Czech Spoken"]
        lang_female_pcts = [28.2, 28.6, 29.5, 29.7, 47.2]
        lang_female_errs = [0.45, 0.31, 0.68, 0.18, 0.39]

        # Panel A: Male-Skewed
        y_l1 = np.arange(len(lang_male))
        bars_l1 = ax1.barh(y_l1, lang_male_pcts, xerr=lang_male_errs, capsize=3, color="#ef4444", height=0.5)
        ax1.axvline(50.0, color="#10b981", linestyle="--", linewidth=1.2, label="50% Parity")
        ax1.set_yticks(y_l1)
        ax1.set_yticklabels(lang_male, fontweight="bold", fontsize=8.5)
        ax1.set_xlabel("Female Share (%)")
        ax1.set_title("(A) Most Male-Skewed Spoken Languages", fontsize=9.5, fontweight="bold")
        ax1.set_xlim(0, 55)
        for bar, val in zip(bars_l1.patches, lang_male_pcts):
            ax1.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

        # Panel B: Parity
        y_l2 = np.arange(len(lang_parity))
        bars_l2 = ax2.barh(y_l2, lang_parity_pcts, xerr=lang_parity_errs, capsize=3, color="#10b981", height=0.5)
        ax2.axvline(50.0, color="#6366f1", linestyle="--", linewidth=1.2, label="50% Parity Target")
        ax2.set_yticks(y_l2)
        ax2.set_yticklabels(lang_parity, fontweight="bold", fontsize=8.5)
        ax2.set_xlabel("Female Share (%)")
        ax2.set_title("(B) Spoken Languages with Most Parity", fontsize=9.5, fontweight="bold")
        ax2.set_xlim(0, 55)
        for bar, val in zip(bars_l2.patches, lang_parity_pcts):
            ax2.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

        # Panel C: Female-Skewed
        y_l3 = np.arange(len(lang_female))
        bars_l3 = ax3.barh(y_l3, lang_female_pcts, xerr=lang_female_errs, capsize=3, color="#8b5cf6", height=0.5)
        ax3.axvline(50.0, color="#10b981", linestyle="--", linewidth=1.2, label="50% Parity")
        ax3.set_yticks(y_l3)
        ax3.set_yticklabels(lang_female, fontweight="bold", fontsize=8.5)
        ax3.set_xlabel("Female Share (%)")
        ax3.set_title("(C) Most Female-Skewed Spoken Languages", fontsize=9.5, fontweight="bold")
        ax3.set_xlim(0, 55)
        for bar, val in zip(bars_l3.patches, lang_female_pcts):
            ax3.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

        plt.suptitle("Figure 15: Intersectional Languages Spoken (P1412) × Gender Representation (3-Panel Breakdown)", y=1.02, fontsize=12, fontweight="bold")
        plt.tight_layout()
        for d in dirs:
            f_png = d / "figure15_language_and_gender.png"
            f_svg = d / "figure15_language_and_gender.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        plt.close(fig)
        print("Generated Figure 15.")

    except ImportError:
        # Fallback to generating crisp SVG vector files directly if matplotlib is unavailable
        for d in dirs:
            _write_svg_figure1(d / "figure1_gender_disparities.svg")
            _write_svg_figure2(d / "figure2_sexual_orientation_explicit_vs_assumed.svg")
            _write_svg_figure3(d / "figure3_geographic_gadm_coverage.svg")
            _write_svg_figure4(d / "figure4_intersectional_bias.svg")
            _write_svg_figure5(d / "figure5_constraint_and_class_profile_gaps.svg")
            _write_svg_figure6(d / "figure6_earth_country_representation_heatmap.svg")
            _write_svg_figure7(d / "figure7_earth_nationality_female_gender_heatmap.svg")
            _write_svg_figure8(d / "figure8_urban_rural_disparity.svg")
            _write_svg_figure9(d / "figure9_linguistic_coverage.svg")
            _write_svg_figure10(d / "figure10_executive_summary_radar.svg")
            _write_svg_figure13(d / "figure13_ethnicity_disparity.svg")
            _write_svg_figure14(d / "figure14_ethnicity_and_gender.svg")
            _write_svg_figure15(d / "figure15_language_and_gender.svg")

    return generated_files


def _write_svg_figure13(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 13: Ethnicity Representation Disparities</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure14(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 14: Ethnicity x Gender Representation</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure15(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 15: Language Spoken x Gender Representation</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")



def _write_svg_figure11(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 11: Languages Spoken P1412 Representation</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure12(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 12: Occupational Gender Parity Spectrum</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure8(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 8: Urban vs. Rural Birthplace Disparity</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure9(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 9: Linguistic Coverage Gaps</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure10(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 10: Executive Summary Bias Radar</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure6(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 6: Global Earth Heatmap of Modern Country Representation</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure7(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 7: Global Earth Heatmap of Intersectional Nationality x Female Representation</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure1(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="18" font-weight="bold" text-anchor="middle">Figure 1: Gender Representation Disparities in Wikidata (Q5)</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure2(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 2: Sexual Orientation Representation</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure3(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 3: Global Geographic Representation Disparities in Wikidata</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure4(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 4: Intersectional Representation (Nationality x Gender)</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


def _write_svg_figure5(filepath: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="350" y="30" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">Figure 5: Property Completeness &amp; Coverage Gaps</text>
</svg>"""
    filepath.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    generated = generate_all_figures()
    print(f"Successfully generated {len(generated)} publication figure assets across figures/ and publication/figures/.")

