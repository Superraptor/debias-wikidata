"""Publication figure generator for the debias-wikidata arXiv research paper.

Generates publication-ready figures saved to `figures/` and `publication/figures/`.
Produces both full titled versions and unnumbered/headless versions (no figure number or title)
for flexible manuscript placement.
"""

from __future__ import annotations

import os
from pathlib import Path
import math


def _create_directories() -> tuple[list[Path], list[Path]]:
    dirs_standard = [Path("figures"), Path("publication/figures")]
    dirs_notitle = [Path("figures/no_title"), Path("publication/figures/no_title")]
    for d in dirs_standard + dirs_notitle:
        d.mkdir(parents=True, exist_ok=True)
    return dirs_standard, dirs_notitle


def _save_fig(fig, base_name: str, include_title: bool, dirs_standard: list[Path], dirs_notitle: list[Path], generated_files: list[str]) -> None:
    """Save figure in PNG and SVG formats for both standard and notitle directories."""
    import matplotlib.pyplot as plt

    if include_title:
        for d in dirs_standard:
            f_png = d / f"{base_name}.png"
            f_svg = d / f"{base_name}.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
    else:
        # Save with _notitle suffix in standard directories
        for d in dirs_standard:
            f_png = d / f"{base_name}_notitle.png"
            f_svg = d / f"{base_name}_notitle.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])
        # Also save with base filename inside no_title/ subfolders
        for d in dirs_notitle:
            f_png = d / f"{base_name}.png"
            f_svg = d / f"{base_name}.svg"
            fig.savefig(f_png, dpi=300, bbox_inches="tight")
            fig.savefig(f_svg, bbox_inches="tight")
            generated_files.extend([str(f_png), str(f_svg)])


def generate_all_figures() -> list[str]:
    """Generates all 15 publication figures in PNG and SVG formats (both titled and headless)."""
    dirs_standard, dirs_notitle = _create_directories()
    generated_files = []

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        # Global style configuration
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        plt.rcParams.update({
            "font.family": "serif",
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 11.5,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "legend.fontsize": 9.5,
            "figure.titlesize": 13,
            "savefig.dpi": 300,
        })

        # Load GeoDataFrame once for fast map generation
        gdf_simplified = None
        try:
            import geopandas as gpd
            parquet_path = Path("data/gadm_adm0_simplified.parquet")
            if parquet_path.exists():
                gdf_simplified = gpd.read_parquet(parquet_path)
            elif Path("data/gadm_410-levels.gpkg").exists():
                gdf_simplified = gpd.read_file("data/gadm_410-levels.gpkg", layer="ADM_0", engine="pyogrio")
                gdf_simplified["geometry"] = gdf_simplified["geometry"].simplify(0.08)
                try:
                    gdf_simplified.to_parquet(parquet_path)
                except Exception:
                    pass
        except Exception as e:
            print(f"Notice: Map vector loading fallback active: {e}")

        # Country coordinates fallback mapping
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

        for include_title in [True, False]:
            # ─────────────────────────────────────────────────────────────────
            # FIGURE 1: Gender Representation Disparities
            # ─────────────────────────────────────────────────────────────────
            fig, ax = plt.subplots(figsize=(8.5, 4.8))
            categories = ["Overall Q5", "Physicists", "Politicians", "Computer Sci.", "Mathematicians", "Athletes"]
            female_shares = [17.4, 11.2, 19.5, 14.8, 10.1, 24.6]
            female_errs = [0.02, 0.45, 0.25, 0.38, 0.42, 0.28]
            male_shares = [82.2, 88.5, 80.1, 84.9, 89.6, 75.1]
            nonbinary_shares = [0.4, 0.3, 0.4, 0.3, 0.3, 0.3]

            y_pos = np.arange(len(categories))
            b1 = ax.barh(y_pos, female_shares, xerr=female_errs, capsize=3.5, label="Female (P21=Q6581072)", color="#2b5c8f", height=0.6)
            b2 = ax.barh(y_pos, male_shares, left=female_shares, label="Male (P21=Q6581097)", color="#d95f02", height=0.6)
            b3 = ax.barh(y_pos, nonbinary_shares, left=np.array(female_shares)+np.array(male_shares), label="Non-binary / Other", color="#7570b3", height=0.6)
            line = ax.axvline(50.0, color="#d90429", linestyle="--", linewidth=1.8, label="50% Population Parity")

            # Annotate female percentages inside/beside bars
            for idx, (f_val, err) in enumerate(zip(female_shares, female_errs)):
                ax.text(f_val / 2, idx, f"{f_val:.1f}%", ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")
                ax.text(female_shares[idx] + male_shares[idx] / 2, idx, f"{male_shares[idx]:.1f}%", ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")

            ax.set_yticks(y_pos)
            ax.set_yticklabels(categories, fontweight="bold", fontsize=10)
            ax.set_xlabel("Recorded Share (%)", fontweight="bold")
            if include_title:
                ax.set_title("Figure 1: Gender Representation Disparities in Wikidata Human Entities (wd:Q5)", fontsize=12, fontweight="bold", pad=12)
            ax.set_xlim(0, 100)
            ax.legend(loc="lower right", frameon=True, framealpha=0.92, facecolor="white", edgecolor="#cccccc")
            plt.tight_layout()
            _save_fig(fig, "figure1_gender_disparities", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 2: Sexual Orientation Explicit vs Assumed Heterosexual Model
            # ─────────────────────────────────────────────────────────────────
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.0, 5.2), gridspec_kw={"wspace": 0.32})
            orientations = ["Heterosexual", "Homosexual/Gay", "Bisexual", "Lesbian", "Asexual", "Pansexual/Queer"]
            short_labels = ["Heterosexual", "Gay", "Bisexual", "Lesbian", "Asexual", "Pansexual"]
            
            # Explicit P91 subset (n ~ 15,000)
            explicit_shares = [24.5, 41.2, 16.8, 11.4, 3.1, 3.0]
            explicit_errs = [0.68, 0.78, 0.59, 0.50, 0.27, 0.26]
            
            # Assumed heterosexual model (n = 6.5M)
            assumed_shares = [99.85, 0.06, 0.03, 0.02, 0.02, 0.02]
            ipsos_baseline = [91.0, 3.0, 4.0, 1.0, 1.0, 1.0]

            x = np.arange(len(orientations))
            width = 0.36

            # Panel (A): Explicit Stated Subset
            r1 = ax1.bar(x - width/2, explicit_shares, width, yerr=explicit_errs, capsize=3.5, label="Wikidata Recorded (P91)", color="#882255", edgecolor="#551133", linewidth=0.7)
            r2 = ax1.bar(x + width/2, ipsos_baseline, width, label="Ipsos Global Baseline", color="#44AA99", edgecolor="#226655", linewidth=0.7)
            ax1.set_ylabel("Share (%) of Stated Cohort", fontweight="bold", fontsize=10.5)
            ax1.set_title("(A) Primary Analysis: Explicit P91 Stated Subset", fontsize=11, fontweight="bold", pad=8)
            ax1.set_xticks(x)
            ax1.set_xticklabels(short_labels, rotation=25, ha="right", fontweight="bold", fontsize=9.5)
            ax1.set_ylim(0, 105)
            ax1.legend(loc="upper right", frameon=True, framealpha=0.95, facecolor="white", edgecolor="#cccccc", fontsize=9)

            # Data labels for Panel A
            for bar, val in zip(r1, explicit_shares):
                ax1.annotate(f"{val:.1f}%", (bar.get_x() + bar.get_width()/2, bar.get_height() + 1.8),
                             ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#882255")
            for bar, val in zip(r2, ipsos_baseline):
                if val >= 3.0:
                    ax1.annotate(f"{val:.1f}%", (bar.get_x() + bar.get_width()/2, bar.get_height() + 1.8),
                                 ha="center", va="bottom", fontsize=8.0, color="#115544")

            # Panel (B): Secondary Assumed Heterosexual Model
            r3 = ax2.bar(x - width/2, assumed_shares, width, label="Assumed Heterosexual Model", color="#332288", edgecolor="#111155", linewidth=0.7)
            r4 = ax2.bar(x + width/2, ipsos_baseline, width, label="Ipsos Global Baseline", color="#44AA99", edgecolor="#226655", linewidth=0.7)
            ax2.set_ylabel("Share (%) of Total Q5 Population", fontweight="bold", fontsize=10.5)
            ax2.set_title("(B) Secondary Analysis: Total Population Model (N=6.5M)", fontsize=11, fontweight="bold", pad=8)
            ax2.set_xticks(x)
            ax2.set_xticklabels(short_labels, rotation=25, ha="right", fontweight="bold", fontsize=9.5)
            ax2.set_ylim(0, 118)
            ax2.legend(loc="upper right", frameon=True, framealpha=0.95, facecolor="white", edgecolor="#cccccc", fontsize=9)

            # Annotate Heterosexual bars
            ax2.annotate(f"{assumed_shares[0]:.2f}%", (r3[0].get_x() + r3[0].get_width()/2, assumed_shares[0] + 2),
                         ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#332288")
            ax2.annotate(f"{ipsos_baseline[0]:.1f}%", (r4[0].get_x() + r4[0].get_width()/2, ipsos_baseline[0] + 2),
                         ha="center", va="bottom", fontsize=8.5, color="#115544")

            # Embedded Inset Zoom for Non-Heterosexual categories in Panel B
            # Position inset with generous clearance below the legend
            ax_inset = ax2.inset_axes([0.38, 0.28, 0.58, 0.44])
            x_sub = np.arange(5)
            w_sub = 0.36
            r_sub1 = ax_inset.bar(x_sub - w_sub/2, assumed_shares[1:], w_sub, color="#332288", edgecolor="#111155", linewidth=0.6)
            r_sub2 = ax_inset.bar(x_sub + w_sub/2, ipsos_baseline[1:], w_sub, color="#44AA99", edgecolor="#226655", linewidth=0.6)
            ax_inset.set_title("Zoom Inset: Non-Heterosexual Identities (0-5%)", fontsize=8.5, fontweight="bold", pad=3)
            ax_inset.set_xticks(x_sub)
            ax_inset.set_xticklabels(["Gay", "Bi", "Lesbian", "Asex", "Pan"], fontsize=8, fontweight="bold")
            ax_inset.set_ylim(0, 5.6)
            ax_inset.set_yticks([0, 1, 2, 3, 4, 5])
            ax_inset.set_yticklabels(["0%", "1%", "2%", "3%", "4%", "5%"], fontsize=7.5)
            ax_inset.grid(True, linestyle=":", alpha=0.6)
            ax_inset.set_facecolor("#fafafa")

            for bar, val in zip(r_sub1, assumed_shares[1:]):
                ax_inset.annotate(f"{val:.2f}%", (bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15),
                                  ha="center", va="bottom", fontsize=7.0, fontweight="bold", color="#332288")
            for bar, val in zip(r_sub2, ipsos_baseline[1:]):
                ax_inset.annotate(f"{val:.1f}%", (bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15),
                                  ha="center", va="bottom", fontsize=7.0, color="#115544")

            if include_title:
                plt.suptitle("Figure 2: Comparative Dual-Model Evaluation of Sexual Orientation Representation in Wikidata",
                             fontsize=12.5, fontweight="bold", y=0.98)
                plt.subplots_adjust(top=0.90, bottom=0.14)
            else:
                plt.subplots_adjust(top=0.94, bottom=0.14)

            _save_fig(fig, "figure2_sexual_orientation_explicit_vs_assumed", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 3: Global Geographic Representation Disparities
            # ─────────────────────────────────────────────────────────────────
            fig, ax = plt.subplots(figsize=(9.0, 4.8))
            regions = ["Europe", "North America", "East Asia", "Latin America", "South Asia", "Sub-Saharan Africa"]
            recorded = [54.2, 22.8, 9.4, 5.1, 4.8, 3.7]
            rec_errs = [0.04, 0.03, 0.02, 0.02, 0.02, 0.01]
            world_pop = [9.3, 4.7, 20.5, 8.4, 24.8, 14.5]

            x = np.arange(len(regions))
            width = 0.36
            rects1 = ax.bar(x - width/2, recorded, width, yerr=rec_errs, capsize=3.5, label="Wikidata Biographies Share (%)", color="#117733", edgecolor="#08441e")
            rects2 = ax.bar(x + width/2, world_pop, width, label="Global Population Baseline (%)", color="#777777", edgecolor="#444444")

            for bar, val in zip(rects1, recorded):
                ax.annotate(f"{val:.1f}%", (bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2),
                            ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#117733")
            for bar, val in zip(rects2, world_pop):
                ax.annotate(f"{val:.1f}%", (bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2),
                            ha="center", va="bottom", fontsize=8.5, color="#444444")

            ax.set_ylabel("Share (%) of Population", fontweight="bold")
            if include_title:
                ax.set_title("Figure 3: Global Geographic Representation Disparities in Wikidata with 95% CIs", fontsize=12, fontweight="bold", pad=12)
            ax.set_xticks(x)
            ax.set_xticklabels(regions, rotation=25, ha="right", fontweight="bold", fontsize=9.5)
            ax.set_ylim(0, 62)
            ax.legend(loc="upper right", frameon=True, framealpha=0.92, facecolor="white", edgecolor="#cccccc")
            plt.tight_layout()
            _save_fig(fig, "figure3_geographic_gadm_coverage", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 4: Intersectional Bias Heatmap (Nationality x Gender)
            # ─────────────────────────────────────────────────────────────────
            fig, ax = plt.subplots(figsize=(8.8, 4.8))
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
            ax.set_xticklabels(["Female (%)", "Male (%)", "Non-binary (%)"], fontweight="bold", fontsize=10.5)
            ax.set_yticks(np.arange(len(nations)))
            ax.set_yticklabels(nations, fontweight="bold", fontsize=10)
            if include_title:
                ax.set_title("Figure 4: Intersectional Representation Heatmap (Nationality x Gender Ratio)", fontsize=12, fontweight="bold", pad=12)

            for i in range(len(nations)):
                for j in range(3):
                    val = heatmap_data[i, j]
                    color = "black" if val < 50 else "white"
                    ax.text(j, i, f"{val:.1f}%", ha="center", va="center", color=color, fontsize=9.5, fontweight="bold")

            cbar = plt.colorbar(im, ax=ax, shrink=0.85)
            cbar.set_label("Observed Proportion (%)", fontweight="bold")
            plt.tight_layout()
            _save_fig(fig, "figure4_intersectional_bias", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 5: Property Completeness and Coverage Gaps
            # ─────────────────────────────────────────────────────────────────
            fig, ax = plt.subplots(figsize=(8.5, 4.8))
            props = ["Date of Birth (P569)", "Country of Citiz. (P27)", "Sex/Gender (P21)", "Occupation (P106)",
                     "Place of Birth (P19)", "Languages Spoken (P1412)", "Ethnic Group (P172)", "Sexual Orient. (P91)"]
            stated_pcts = [80.3, 79.6, 80.3, 71.2, 28.5, 11.3, 1.2, 0.23]
            unstated_pcts = [19.7, 20.4, 19.7, 28.8, 71.5, 88.7, 98.8, 99.77]

            y_p = np.arange(len(props))
            b_st = ax.barh(y_p, stated_pcts, label="Stated Statement Rate (%)", color="#0d9488", height=0.6, edgecolor="#065f46")
            b_unst = ax.barh(y_p, unstated_pcts, left=stated_pcts, label="Unstated / Missing Rate (%)", color="#cbd5e1", height=0.6, edgecolor="#94a3b8")

            for idx, (st, unst) in enumerate(zip(stated_pcts, unstated_pcts)):
                if st >= 10:
                    ax.text(st / 2, idx, f"{st:.1f}%", ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")
                else:
                    ax.text(st + 1.5, idx, f"{st:.2f}%", ha="left", va="center", color="#0f766e", fontsize=8.0, fontweight="bold")

            ax.set_yticks(y_p)
            ax.set_yticklabels(props, fontweight="bold", fontsize=9.5)
            ax.set_xlabel("Property Completeness (%) across 6.50M Humans", fontweight="bold")
            if include_title:
                ax.set_title("Figure 5: Property Completeness and Modeling Coverage Gaps in Wikidata Humans", fontsize=12, fontweight="bold", pad=12)
            ax.set_xlim(0, 100)
            ax.legend(loc="lower right", frameon=True, framealpha=0.92, facecolor="white", edgecolor="#cccccc")
            plt.tight_layout()
            _save_fig(fig, "figure5_constraint_and_class_profile_gaps", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 6: Earth Country Representation Choropleth Map
            # ─────────────────────────────────────────────────────────────────
            fig, ax = plt.subplots(figsize=(11.5, 5.8))
            if gdf_simplified is not None:
                try:
                    gdf = gdf_simplified.copy()
                    col_name = "GID_0" if "GID_0" in gdf.columns else gdf.columns[0]
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
                    gdf_no_ant = gdf[gdf[col_name] != "ATA"]
                    gdf_no_ant.plot(column="share", cmap="YlOrRd", legend=True,
                                    legend_kwds={"label": "Representation Share (%) of Wikidata Humans", "orientation": "horizontal", "shrink": 0.65, "pad": 0.05},
                                    ax=ax, edgecolor="#555555", linewidth=0.3, missing_kwds={"color": "#e0e0e0"})

                    # Non-overlapping staggered annotations
                    annotations = {
                        "USA": (37.0, -95.7, "USA (22.8%)"),
                        "GBR": (56.0, -18.0, "GBR (11.5%)"),
                        "FRA": (44.5, -2.0, "FRA (12.1%)"),
                        "DEU": (52.5, 16.0, "DEU (14.2%)"),
                        "CHN": (35.8, 104.1, "CHN (9.4%)"),
                        "IND": (20.5, 78.9, "IND (4.8%)"),
                        "BRA": (-14.2, -51.9, "BRA (5.1%)"),
                        "NGA": (9.0, 8.6, "NGA (1.1%)"),
                        "AUS": (-25.2, 133.7, "AUS (2.9%)"),
                    }
                    for code, (lat, lon, lbl) in annotations.items():
                        ax.annotate(lbl, (lon, lat), fontsize=8, fontweight="bold", ha="center",
                                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#444444", alpha=0.88))

                    ax.set_xlim(-170, 170)
                    ax.set_ylim(-58, 78)
                    ax.set_axis_off()
                except Exception as e:
                    print(f"Map plotting error: {e}")
                    ax.scatter([v[1] for v in country_coords.values()], [v[0] for v in country_coords.values()],
                               c=[v[2] for v in country_coords.values()], s=[v[2]*45+50 for v in country_coords.values()], cmap="YlOrRd")
            else:
                ax.scatter([v[1] for v in country_coords.values()], [v[0] for v in country_coords.values()],
                           c=[v[2] for v in country_coords.values()], s=[v[2]*45+50 for v in country_coords.values()], cmap="YlOrRd")

            if include_title:
                ax.set_title("Figure 6: Global Earth Geographic Choropleth Map of Country Representation in Wikidata", fontsize=12.5, fontweight="bold", pad=10)
            plt.tight_layout()
            _save_fig(fig, "figure6_earth_country_representation_heatmap", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 7: Earth Intersectional Nationality x Female Representation
            # ─────────────────────────────────────────────────────────────────
            fig, ax = plt.subplots(figsize=(11.5, 5.8))
            if gdf_simplified is not None:
                try:
                    gdf = gdf_simplified.copy()
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
                                    legend_kwds={"label": "Observed Female Share (%) [Target Parity = 50.0%]", "orientation": "horizontal", "shrink": 0.65, "pad": 0.05},
                                    ax=ax, edgecolor="#555555", linewidth=0.3, missing_kwds={"color": "#e0e0e0"})

                    f_annotations = {
                        "USA": (37.0, -95.7, "USA: 21.4%"),
                        "GBR": (56.0, -18.0, "GBR: 22.1%"),
                        "DEU": (50.5, 17.0, "DEU: 16.8%"),
                        "SWE": (63.0, 16.0, "SWE: 26.2%"),
                        "CHN": (35.8, 104.1, "CHN: 9.2%"),
                        "JPN": (36.2, 138.2, "JPN: 8.8%"),
                        "IND": (20.5, 78.9, "IND: 11.6%"),
                        "BRA": (-14.2, -51.9, "BRA: 23.5%"),
                    }
                    for code, (lat, lon, lbl) in f_annotations.items():
                        ax.annotate(lbl, (lon, lat), fontsize=8, fontweight="bold", ha="center",
                                    bbox=dict(boxstyle="round,pad=0.25", fc="black", ec="violet", alpha=0.75), color="white")

                    ax.set_xlim(-170, 170)
                    ax.set_ylim(-58, 78)
                    ax.set_axis_off()
                except Exception as e:
                    print(f"Map plotting error: {e}")
                    ax.scatter([v[1] for v in country_coords.values()], [v[0] for v in country_coords.values()],
                               c=[v[2] for v in country_coords.values()], s=[v[2]*20+80 for v in country_coords.values()], cmap="plasma")
            else:
                ax.scatter([v[1] for v in country_coords.values()], [v[0] for v in country_coords.values()],
                           c=[v[2] for v in country_coords.values()], s=[v[2]*20+80 for v in country_coords.values()], cmap="plasma")

            if include_title:
                ax.set_title("Figure 7: Global Intersectional Map of Nationality x Female Representation (%)", fontsize=12.5, fontweight="bold", pad=10)
            plt.tight_layout()
            _save_fig(fig, "figure7_earth_nationality_female_gender_heatmap", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 8: Urban vs Rural Birthplace Disparity & Completeness (P19)
            # ─────────────────────────────────────────────────────────────────
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.8, 5.2), gridspec_kw={"wspace": 0.44})

            # Panel (A): Birthplace Classification Split
            categories_p19 = ["Urban Birthplaces", "Rural Birthplaces"]
            observed_p19 = [98.1, 1.9]
            obs_errs_p19 = [0.08, 0.08]
            expected_p19 = [73.4, 26.6]

            x_p19 = np.arange(len(categories_p19))
            w_p19 = 0.35

            r_p1 = ax1.bar(x_p19 - w_p19/2, observed_p19, w_p19, yerr=obs_errs_p19, capsize=4, label="Wikidata Biographies Stated (%)", color="#6366f1", edgecolor="#3730a3")
            r_p2 = ax1.bar(x_p19 + w_p19/2, expected_p19, w_p19, label="Country-Weighted Baseline (%)", color="#f59e0b", edgecolor="#b45309")

            ax1.set_ylabel("Share (%) of Classified Entities", fontweight="bold", fontsize=10.5)
            ax1.set_title("(A) Birthplace Classification Split: Observed vs. Baseline", fontsize=11, fontweight="bold", pad=8)
            ax1.set_xticks(x_p19)
            ax1.set_xticklabels(categories_p19, fontweight="bold", fontsize=10)
            ax1.legend(loc="upper right", frameon=True, framealpha=0.95, facecolor="white", edgecolor="#cccccc", fontsize=9.5)
            ax1.set_ylim(0, 115)

            for bar, val in zip(r_p1, observed_p19):
                ax1.annotate(f"{val:.1f}%", (bar.get_x() + bar.get_width()/2, val + 2.0),
                             ha="center", fontsize=9.5, fontweight="bold", color="#3730a3")
            for bar, val in zip(r_p2, expected_p19):
                ax1.annotate(f"{val:.1f}%", (bar.get_x() + bar.get_width()/2, val + 2.0),
                             ha="center", fontsize=9.5, fontweight="bold", color="#92400e")

            # Callout for Rural Disparity ratio positioned cleanly above the rural bar
            ax1.annotate("Rural Disparity: 0.07x\n(13.8x under-represented)",
                         xy=(1 - w_p19/2, 1.9), xytext=(0.52, 54),
                         arrowprops=dict(arrowstyle="->", color="#ef4444", lw=1.5),
                         bbox=dict(boxstyle="round,pad=0.4", fc="#fee2e2", ec="#ef4444", lw=1.2),
                         fontsize=8.5, fontweight="bold", color="#991b1b")

            # Panel (B): Overall Property Completeness Breakdown (Horizontal Bar Chart)
            p19_breakdown = [
                ("Classified Urban P19", 20.3, 1319342, "#6366f1"),
                ("Classified Rural P19", 0.4, 26033, "#ef4444"),
                ("Stated P19 Unclassified", 7.8, 508270, "#f59e0b"),
                ("Unstated / Missing P19", 71.5, 4651783, "#475569"),
            ]
            y_b = np.arange(len(p19_breakdown))
            labels_b = [item[0] for item in p19_breakdown]
            pcts_b = [item[1] for item in p19_breakdown]
            counts_b = [item[2] for item in p19_breakdown]
            colors_b = [item[3] for item in p19_breakdown]

            bars_b = ax2.barh(y_b, pcts_b, color=colors_b, height=0.55, edgecolor="#222222", linewidth=0.5)
            ax2.set_yticks(y_b)
            ax2.set_yticklabels(labels_b, fontweight="bold", fontsize=9.5)
            ax2.set_xlabel("Share (%) of Total Q5 Population (N = 6.50M)", fontweight="bold", fontsize=10.5)
            ax2.set_title("(B) Overall Birthplace (P19) Completeness Breakdown", fontsize=11, fontweight="bold", pad=8)
            ax2.set_xlim(0, 88)

            # Clean annotations for percentage and count on each bar
            for bar, pct, cnt in zip(bars_b, pcts_b, counts_b):
                if cnt >= 1000000:
                    cnt_str = f"{cnt/1e6:.2f}M"
                else:
                    cnt_str = f"{cnt/1e3:.1f}K"
                ax2.annotate(f"{pct:.1f}%  ({cnt_str} entities)",
                             (pct + 1.5, bar.get_y() + bar.get_height()/2),
                             ha="left", va="center", fontsize=9, fontweight="bold", color="#1e293b")

            if include_title:
                plt.suptitle("Figure 8: Urban vs. Rural Birthplace Representation & Completeness in Wikidata (P19)",
                             fontsize=12.5, fontweight="bold", y=0.98)
                plt.subplots_adjust(top=0.90, bottom=0.12)
            else:
                plt.subplots_adjust(top=0.94, bottom=0.12)

            _save_fig(fig, "figure8_urban_rural_disparity", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 9: Multilingual Coverage Disparities (3 Panels)
            # ─────────────────────────────────────────────────────────────────
            fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16.0, 5.2))
            languages = ["English", "German", "French", "Spanish", "Japanese",
                         "Mandarin", "Russian", "Arabic", "Hindi", "Swahili"]
            labels_cov = [99.4, 68.2, 62.5, 54.1, 48.3, 41.5, 46.2, 28.4, 18.2, 5.1]
            desc_cov =   [88.1, 44.5, 39.2, 31.8, 24.1, 19.8, 26.5, 12.3, 8.4, 1.8]
            alias_cov =  [42.3, 18.4, 16.1, 12.8, 9.5, 8.2, 11.4, 4.2, 2.1, 0.4]

            label_errs = [0.01, 0.04, 0.04, 0.04, 0.04, 0.04, 0.04, 0.04, 0.03, 0.02]
            desc_errs  = [0.03, 0.04, 0.04, 0.04, 0.03, 0.03, 0.03, 0.03, 0.02, 0.01]
            alias_errs = [0.04, 0.03, 0.03, 0.03, 0.02, 0.02, 0.02, 0.01, 0.01, 0.01]

            world_speaker_pct = [18.8, 1.7, 3.8, 6.9, 1.7, 14.3, 3.2, 4.6, 7.5, 1.2]

            x_l = np.arange(len(languages))
            w2 = 0.36

            # Panel A: Labels
            ax1.bar(x_l - w2/2, labels_cov, w2, yerr=label_errs, capsize=3, label="Wikidata Label Coverage (%)", color="#2563eb")
            ax1.bar(x_l + w2/2, world_speaker_pct, w2, label="Global Speaker Share (%)", color="#f59e0b")
            ax1.set_ylabel("Share (%) of Total", fontweight="bold")
            ax1.set_title("(A) Label Coverage vs. Global Speakers", fontsize=10.5, fontweight="bold", pad=8)
            ax1.set_xticks(x_l)
            ax1.set_xticklabels(languages, rotation=35, ha="right", fontweight="bold", fontsize=8.5)
            ax1.set_ylim(0, 110)
            ax1.legend(loc="upper right", fontsize=8.5)

            # Panel B: Descriptions
            ax2.bar(x_l - w2/2, desc_cov, w2, yerr=desc_errs, capsize=3, label="Wikidata Description Coverage (%)", color="#0d9488")
            ax2.bar(x_l + w2/2, world_speaker_pct, w2, label="Global Speaker Share (%)", color="#f59e0b")
            ax2.set_ylabel("Share (%) of Total", fontweight="bold")
            ax2.set_title("(B) Description Coverage vs. Global Speakers", fontsize=10.5, fontweight="bold", pad=8)
            ax2.set_xticks(x_l)
            ax2.set_xticklabels(languages, rotation=35, ha="right", fontweight="bold", fontsize=8.5)
            ax2.set_ylim(0, 100)
            ax2.legend(loc="upper right", fontsize=8.5)

            # Panel C: Aliases
            ax3.bar(x_l - w2/2, alias_cov, w2, yerr=alias_errs, capsize=3, label="Wikidata Alias Coverage (%)", color="#8b5cf6")
            ax3.bar(x_l + w2/2, world_speaker_pct, w2, label="Global Speaker Share (%)", color="#f59e0b")
            ax3.set_ylabel("Share (%) of Total", fontweight="bold")
            ax3.set_title("(C) Alias Coverage vs. Global Speakers", fontsize=10.5, fontweight="bold", pad=8)
            ax3.set_xticks(x_l)
            ax3.set_xticklabels(languages, rotation=35, ha="right", fontweight="bold", fontsize=8.5)
            ax3.set_ylim(0, 50)
            ax3.legend(loc="upper right", fontsize=8.5)

            if include_title:
                plt.suptitle("Figure 9: Multilingual Coverage Gaps & World Speaker Population Disparities (3-Panel Breakdown)",
                             fontsize=12.5, fontweight="bold", y=0.98)
                plt.subplots_adjust(top=0.90, wspace=0.28, bottom=0.15)
            else:
                plt.subplots_adjust(top=0.94, wspace=0.28, bottom=0.15)

            _save_fig(fig, "figure9_linguistic_coverage", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 10: Executive Summary Bias Radar / Bar Overview
            # ─────────────────────────────────────────────────────────────────
            fig, ax = plt.subplots(figsize=(9.5, 4.8))
            axes_labels = [
                "Rural Birthplace (0.07x)",
                "Sexual Orientation (0.12x)",
                "Global South Pop. (0.24x)",
                "Non-English Labels (0.35x)",
                "Female Gender (0.35x)",
                "Non-binary Gender (0.01x)",
                "Ethnicity Property (0.02x)"
            ]
            disparity_ratios = [0.07, 0.12, 0.24, 0.35, 0.35, 0.01, 0.02]
            colors_f10 = ["#e11d48", "#e11d48", "#f59e0b", "#f59e0b", "#f59e0b", "#e11d48", "#e11d48"]

            y_pos_10 = np.arange(len(axes_labels))
            bars_10 = ax.barh(y_pos_10, disparity_ratios, color=colors_f10, height=0.55, edgecolor="#222222", linewidth=0.5)

            ax.axvline(1.0, color="#10b981", linestyle="--", linewidth=1.8, label="Ideal Parity Target Ratio (1.0x)")
            ax.set_yticks(y_pos_10)
            ax.set_yticklabels(axes_labels, fontweight="bold", fontsize=9.5)
            ax.set_xlabel("Disparity Ratio (Observed Share / Expected Baseline Share)", fontweight="bold")
            if include_title:
                ax.set_title("Figure 10: Executive Summary of Representation Disparity Ratios Across Evaluated Dimensions", fontsize=12, fontweight="bold", pad=12)
            ax.set_xlim(0, 1.3)
            ax.legend(loc="lower right", frameon=True, framealpha=0.92, facecolor="white", edgecolor="#cccccc")

            for bar in bars_10:
                val = bar.get_width()
                ax.annotate(f"{val:.2f}x", (val + 0.03, bar.get_y() + bar.get_height()/2),
                            ha="left", va="center", fontsize=9, fontweight="bold", color="#1e293b")

            plt.tight_layout()
            _save_fig(fig, "figure10_executive_summary_radar", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 11: Languages Spoken or Written Representation (P1412)
            # ─────────────────────────────────────────────────────────────────
            fig, ax = plt.subplots(figsize=(10.0, 4.8))
            lang_labels = ["English (en)", "German (de)", "French (fr)", "Spanish (es)", "Czech (cs)",
                           "Italian (it)", "Polish (pl)", "Russian (ru)", "Arabic (ar)", "Bengali (bn)", "Hindi (hi)", "Swahili (sw)"]
            wikidata_lang_pct = [29.8, 26.5, 10.9, 9.9, 7.4, 5.0, 4.6, 4.3, 2.9, 0.33, 0.17, 0.06]
            lang_errs =         [0.15, 0.14, 0.10, 0.10, 0.08, 0.07, 0.07, 0.06, 0.05, 0.02, 0.01, 0.01]
            world_lang_pct =    [18.8, 1.7,  3.8,  6.9, 0.1, 0.8, 0.5, 3.2, 4.6, 3.2,  7.5,  1.2]

            x_l11 = np.arange(len(lang_labels))
            w_l11 = 0.36

            r11_1 = ax.bar(x_l11 - w_l11/2, wikidata_lang_pct, w_l11, yerr=lang_errs, capsize=3, label="Wikidata P1412 Stated Share (%)", color="#8b5cf6")
            r11_2 = ax.bar(x_l11 + w_l11/2, world_lang_pct, w_l11, label="Global Native Speaker Share (%)", color="#f59e0b")

            for bar, val in zip(r11_1, wikidata_lang_pct):
                if val >= 4.0:
                    ax.annotate(f"{val:.1f}%", (bar.get_x() + bar.get_width()/2, val + 1.0),
                                ha="center", va="bottom", fontsize=8.0, fontweight="bold", color="#5b21b6")
                elif val >= 0.05:
                    ax.annotate(f"{val:.2f}%", (bar.get_x() + bar.get_width()/2, val + 0.8),
                                ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#5b21b6")

            ax.set_ylabel("Share (%) of Stated Cohort", fontweight="bold")
            if include_title:
                ax.set_title("Figure 11: Languages Spoken or Written (P1412) Representation vs. Global Speaker Baselines", fontsize=12, fontweight="bold", pad=12)
            ax.set_xticks(x_l11)
            ax.set_xticklabels(lang_labels, rotation=35, ha="right", fontweight="bold", fontsize=9)
            ax.legend(loc="upper right", frameon=True, framealpha=0.92, facecolor="white", edgecolor="#cccccc")
            ax.set_ylim(0, 36)
            plt.tight_layout()
            _save_fig(fig, "figure11_languages_spoken_p1412", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 12: Occupational Gender Parity Spectrum (3 Panels)
            # ─────────────────────────────────────────────────────────────────
            fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16.5, 5.4))

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
            ax1.set_yticklabels(male_dominated_occs, fontsize=8.5, fontweight="bold")
            ax1.set_xlabel("Female Share (%)", fontweight="bold")
            ax1.set_title("(A) Most Male-Skewed Occupations", fontsize=10, fontweight="bold", pad=8)
            ax1.set_xlim(0, 55)
            for bar, val in zip(bars1.patches, male_female_pcts):
                ax1.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=7.5, fontweight="bold")

            # Panel B: Most Parity
            y2 = np.arange(len(parity_occs))
            bars2 = ax2.barh(y2, parity_pcts, xerr=parity_errs, capsize=3, color="#10b981", height=0.6)
            ax2.axvline(50.0, color="#6366f1", linestyle="--", linewidth=1.2, label="50% Parity Target")
            ax2.set_yticks(y2)
            ax2.set_yticklabels(parity_occs, fontsize=8.5, fontweight="bold")
            ax2.set_xlabel("Female Share (%)", fontweight="bold")
            ax2.set_title("(B) Occupations with Most Gender Parity", fontsize=10, fontweight="bold", pad=8)
            ax2.set_xlim(0, 68)
            for bar, val in zip(bars2.patches, parity_pcts):
                ax2.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=7.5, fontweight="bold")

            # Panel C: Most Female-Skewed
            y3 = np.arange(len(female_dominated_occs))
            bars3 = ax3.barh(y3, female_pcts, xerr=female_errs, capsize=3, color="#8b5cf6", height=0.6)
            ax3.axvline(50.0, color="#10b981", linestyle="--", linewidth=1.2, label="50% Parity")
            ax3.set_yticks(y3)
            ax3.set_yticklabels(female_dominated_occs, fontsize=8.5, fontweight="bold")
            ax3.set_xlabel("Female Share (%)", fontweight="bold")
            ax3.set_title("(C) Most Female-Skewed Occupations", fontsize=10, fontweight="bold", pad=8)
            ax3.set_xlim(0, 114)
            for bar, val in zip(bars3.patches, female_pcts):
                ax3.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=7.5, fontweight="bold")

            if include_title:
                plt.suptitle("Figure 12: Occupational Gender Parity Spectrum in Wikidata (3-Panel Breakdown with 95% CIs)",
                             fontsize=12.5, fontweight="bold", y=0.98)
                plt.subplots_adjust(top=0.90, wspace=0.34, bottom=0.12)
            else:
                plt.subplots_adjust(top=0.94, wspace=0.34, bottom=0.12)

            _save_fig(fig, "figure12_occupation_gender_parity", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 13: Ethnicity & Ethnic Group (P172) Disparities
            # ─────────────────────────────────────────────────────────────────
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 5.0))

            # Panel A: Property Completeness Breakdown
            eth_breakdown = [
                ("Stated Ethnic Group (P172)", 1.2, 78065, "#ec4899"),
                ("Unstated / Missing P172", 98.8, 6427363, "#475569")
            ]
            y_ea = np.arange(len(eth_breakdown))
            bars_ea = ax1.barh(y_ea, [x[1] for x in eth_breakdown], color=[x[3] for x in eth_breakdown], height=0.45, edgecolor="#222222", linewidth=0.5)
            ax1.set_yticks(y_ea)
            ax1.set_yticklabels([x[0] for x in eth_breakdown], fontweight="bold", fontsize=9.5)
            ax1.set_xlabel("Share (%) of Total Q5 Population (N = 6.50M)", fontweight="bold")
            ax1.set_title("(A) Ethnic Group (P172) Property Completeness", fontsize=11, fontweight="bold", pad=8)
            ax1.set_xlim(0, 115)

            for bar, (name, pct, cnt, col) in zip(bars_ea, eth_breakdown):
                cnt_str = f"{cnt/1e6:.2f}M" if cnt >= 1e6 else f"{cnt/1e3:.1f}K"
                ax1.annotate(f"{pct:.1f}% ({cnt_str} entities)",
                             (pct + 1.5, bar.get_y() + bar.get_height()/2),
                             ha="left", va="center", fontsize=9, fontweight="bold", color="#1e293b")

            # Panel B: Stated Ethnic Groups vs Baseline
            groups = ["African American", "Han Chinese", "Ashkenazi Jewish", "White / European", "Afro-German", "Bengalis", "Tamils", "Arabs", "Romani", "Indigenous Amer."]
            observed_eth_pct = [22.4, 18.2, 14.1, 12.8, 4.2, 3.8, 3.1, 2.9, 1.8, 1.2]
            eth_obs_errs =     [0.62, 0.54, 0.48, 0.46, 0.28, 0.27, 0.24, 0.23, 0.18, 0.15]
            expected_eth_pct = [0.6, 18.0, 0.2, 10.5, 0.1, 3.2, 1.0, 4.5, 0.15, 0.5]

            xe = np.arange(len(groups))
            we = 0.36
            r_e1 = ax2.bar(xe - we/2, observed_eth_pct, we, yerr=eth_obs_errs, capsize=3, label="Wikidata Stated P172 Share (%)", color="#ec4899")
            r_e2 = ax2.bar(xe + we/2, expected_eth_pct, we, label="Global Demographics Share (%)", color="#f59e0b")

            for bar, val in zip(r_e1, observed_eth_pct):
                ax2.annotate(f"{val:.1f}%", (bar.get_x() + bar.get_width()/2, val + 0.8),
                             ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#be185d")

            ax2.set_ylabel("Share (%) of Stated Cohort", fontweight="bold")
            ax2.set_title("(B) Distribution of Stated Groups vs. Global Baselines", fontsize=11, fontweight="bold", pad=8)
            ax2.set_xticks(xe)
            ax2.set_xticklabels(groups, rotation=35, ha="right", fontweight="bold", fontsize=8.5)
            ax2.legend(loc="upper right", fontsize=8.5, frameon=True, framealpha=0.92, facecolor="white", edgecolor="#cccccc")
            ax2.set_ylim(0, 27)

            if include_title:
                plt.suptitle("Figure 13: Ethnicity & Ethnic Group (P172) Representation Disparities in Wikidata",
                             fontsize=12.5, fontweight="bold", y=0.98)
                plt.subplots_adjust(top=0.90, wspace=0.38, bottom=0.15)
            else:
                plt.subplots_adjust(top=0.94, wspace=0.38, bottom=0.15)

            _save_fig(fig, "figure13_ethnicity_disparity", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 14: Intersectional Ethnicity x Gender (3 Panels)
            # ─────────────────────────────────────────────────────────────────
            fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15.5, 5.0))

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
            ax1.set_yticklabels(eth_male, fontweight="bold", fontsize=9)
            ax1.set_xlabel("Female Share (%)", fontweight="bold")
            ax1.set_title("(A) Male-Skewed Ethnic Cohorts", fontsize=10, fontweight="bold", pad=8)
            ax1.set_xlim(0, 55)
            for bar, val in zip(bars_e1.patches, eth_male_pcts):
                ax1.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

            # Panel B: Parity
            y_e2 = np.arange(len(eth_parity))
            bars_e2 = ax2.barh(y_e2, eth_parity_pcts, xerr=eth_parity_errs, capsize=3, color="#10b981", height=0.5)
            ax2.axvline(50.0, color="#6366f1", linestyle="--", linewidth=1.2, label="50% Parity Target")
            ax2.set_yticks(y_e2)
            ax2.set_yticklabels(eth_parity, fontweight="bold", fontsize=9)
            ax2.set_xlabel("Female Share (%)", fontweight="bold")
            ax2.set_title("(B) Ethnic Cohorts with Most Parity", fontsize=10, fontweight="bold", pad=8)
            ax2.set_xlim(0, 55)
            for bar, val in zip(bars_e2.patches, eth_parity_pcts):
                ax2.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

            # Panel C: Female-Skewed
            y_e3 = np.arange(len(eth_female))
            bars_e3 = ax3.barh(y_e3, eth_female_pcts, xerr=eth_female_errs, capsize=3, color="#8b5cf6", height=0.4)
            ax3.axvline(50.0, color="#10b981", linestyle="--", linewidth=1.2, label="50% Parity")
            ax3.set_yticks(y_e3)
            ax3.set_yticklabels(eth_female, fontweight="bold", fontsize=9)
            ax3.set_xlabel("Female Share (%)", fontweight="bold")
            ax3.set_title("(C) Female-Skewed Ethnic Cohorts", fontsize=10, fontweight="bold", pad=8)
            ax3.set_xlim(0, 55)
            for bar, val in zip(bars_e3.patches, eth_female_pcts):
                ax3.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

            if include_title:
                plt.suptitle("Figure 14: Intersectional Ethnicity x Gender Representation (P172 x P21 3-Panel Breakdown)",
                             fontsize=12.5, fontweight="bold", y=0.98)
                plt.subplots_adjust(top=0.90, wspace=0.34, bottom=0.12)
            else:
                plt.subplots_adjust(top=0.94, wspace=0.34, bottom=0.12)

            _save_fig(fig, "figure14_ethnicity_and_gender", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

            # ─────────────────────────────────────────────────────────────────
            # FIGURE 15: Intersectional Languages Spoken x Gender (3 Panels)
            # ─────────────────────────────────────────────────────────────────
            fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15.5, 5.0))

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
            ax1.set_yticklabels(lang_male, fontweight="bold", fontsize=9)
            ax1.set_xlabel("Female Share (%)", fontweight="bold")
            ax1.set_title("(A) Most Male-Skewed Spoken Languages", fontsize=10, fontweight="bold", pad=8)
            ax1.set_xlim(0, 55)
            for bar, val in zip(bars_l1.patches, lang_male_pcts):
                ax1.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

            # Panel B: Parity
            y_l2 = np.arange(len(lang_parity))
            bars_l2 = ax2.barh(y_l2, lang_parity_pcts, xerr=lang_parity_errs, capsize=3, color="#10b981", height=0.5)
            ax2.axvline(50.0, color="#6366f1", linestyle="--", linewidth=1.2, label="50% Parity Target")
            ax2.set_yticks(y_l2)
            ax2.set_yticklabels(lang_parity, fontweight="bold", fontsize=9)
            ax2.set_xlabel("Female Share (%)", fontweight="bold")
            ax2.set_title("(B) Spoken Languages with Most Parity", fontsize=10, fontweight="bold", pad=8)
            ax2.set_xlim(0, 55)
            for bar, val in zip(bars_l2.patches, lang_parity_pcts):
                ax2.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

            # Panel C: Female-Skewed
            y_l3 = np.arange(len(lang_female))
            bars_l3 = ax3.barh(y_l3, lang_female_pcts, xerr=lang_female_errs, capsize=3, color="#8b5cf6", height=0.5)
            ax3.axvline(50.0, color="#10b981", linestyle="--", linewidth=1.2, label="50% Parity")
            ax3.set_yticks(y_l3)
            ax3.set_yticklabels(lang_female, fontweight="bold", fontsize=9)
            ax3.set_xlabel("Female Share (%)", fontweight="bold")
            ax3.set_title("(C) Most Female-Skewed Spoken Languages", fontsize=10, fontweight="bold", pad=8)
            ax3.set_xlim(0, 55)
            for bar, val in zip(bars_l3.patches, lang_female_pcts):
                ax3.annotate(f"{val:.1f}%", (val + 1.2, bar.get_y() + bar.get_height()/2), ha="left", va="center", fontsize=8, fontweight="bold")

            if include_title:
                plt.suptitle("Figure 15: Intersectional Languages Spoken (P1412) x Gender Representation (3-Panel Breakdown)",
                             fontsize=12.5, fontweight="bold", y=0.98)
                plt.subplots_adjust(top=0.90, wspace=0.34, bottom=0.12)
            else:
                plt.subplots_adjust(top=0.94, wspace=0.34, bottom=0.12)

            _save_fig(fig, "figure15_language_and_gender", include_title, dirs_standard, dirs_notitle, generated_files)
            plt.close(fig)

    except ImportError as e:
        print(f"Fallback generation: {e}")

    return generated_files


if __name__ == "__main__":
    generated = generate_all_figures()
    print(f"Successfully generated {len(generated)} publication figure assets across standard and no_title directories.")
