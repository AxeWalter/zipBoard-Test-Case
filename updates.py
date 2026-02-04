import pandas as pd
import os
from scraper import get_articles, llm_topics_analysis
from dotenv import load_dotenv

load_dotenv()
DATA_PATH = os.getenv("DATA_PATH")


def update_spreadsheet():
    updated_data = get_articles()
    df_updated = pd.DataFrame(updated_data)

    #Simple check. If the file doesn't exist, we'll create a new file with the scraped information
    if not os.path.exists(DATA_PATH):
        print(f"The file {DATA_PATH} was not found. Creating new spreadsheet at {DATA_PATH}")
        df_updated.to_excel(DATA_PATH, index=False)
        return

    df_old = pd.read_excel(DATA_PATH)

    #Extract the new URLs with a set comparison, then use pandas to compare each row to the resulted set subtraction
    new_urls = set(df_updated["url"]) - set(df_old["url"])
    df_added = df_updated[df_updated["url"].isin(new_urls)]

    #Puts the old and updated dfs together merging them on the URL. Then we can compare, if the date changed, it was updated
    comparison_df = pd.merge(
        df_old[["url", "last updated"]],
        df_updated[["url", "last updated"]],
        on="url",
        suffixes=("_old", "_new")
    )

    modified_urls = comparison_df[
        (comparison_df["last updated_old"] != comparison_df["last updated_new"])
    ]["url"]

    df_modified = df_updated[df_updated["url"].isin(modified_urls)]

    #First check if there were any changes/new articles, then we only keep the not modified articles in the df_old.
    #After, we concatenate the old df (free of the modified rows) with the df_added (new articles) and df_modified for the modified articles.
    if not df_added.empty or not df_modified.empty:
        print(f"{len(df_added)} new articles were found and {len(df_modified)} modified")
        print("Enriching the information of the new articles...")
        df_to_enrich = pd.concat([df_added, df_modified], ignore_index=True)
        enrich_list = df_to_enrich.to_dict('records')
        enriched_list = llm_topics_analysis(enrich_list)
        df_enriched = pd.DataFrame(enriched_list)

        df_final = df_old[~df_old["url"].isin(modified_urls)]
        df_final = pd.concat([df_final, df_enriched], ignore_index=True)

        df_final["temp_id"] = df_final["article id"].str.extract(r'(\d+)').astype(int)
        df_final = df_final.sort_values(by="temp_id")
        df_final = df_final.drop(columns=["temp_id"])

        df_final.to_excel(DATA_PATH, index=False)
        print("Spreadsheet successfully updated")
    else:
        print("No changes detected in the articles at https://help.zipboard.co")