import requests
from bs4 import BeautifulSoup
import pandas as pd
from google import genai
import os
import json
from dotenv import load_dotenv

URL = "https://help.zipboard.co"


def get_articles():
    data = []
    check_for_dup_urls = set() #To prevent inserting duplicate articles
    article_id = 1

    #First we need to access the main URL
    response = requests.get(URL)
    soup = BeautifulSoup(response.text, "html.parser")
    categories = soup.find_all("a", class_="category") #Finding all the categories in the main URL


    #Here we can access the page of each category, allowing to scrape the articles
    for category in categories:
        category_name = category.find("h3").text.strip()
        category_url = URL + category["href"]

        category_response = requests.get(category_url)
        category_soup = BeautifulSoup(category_response.text, "html.parser")
        articles = category_soup.find("ul", class_="articleList") #Finding all the articles in the category

        if articles:
            articles_links = articles.find_all("a", href=True)

            #Properly access the articles
            for article in articles_links:
                article_url = URL + article["href"]
                if article_url in check_for_dup_urls: #Check for duplicity
                    continue

                check_for_dup_urls.add(article_url)
                article_title = article.find("span").text.strip()

                article_response = requests.get(article_url)
                article_soup = BeautifulSoup(article_response.text, "html.parser")

                article_body = article_soup.find("article")
                full_text = article_body.get_text(separator=" ")

                word_count = len(full_text.split())
                bool_screenshots = "Yes" if article_body.find("img") else "No"
                bool_video = "Yes" if article_body.find("iframe") or article_body.find("video") else "No"

                time_tag = article_soup.find("time", class_="lu")
                if time_tag and time_tag.has_attr("datetime"):
                    last_updated = time_tag["datetime"]
                else:
                    last_updated = "Unknown"

                content_classification = "How-to Guide"
                if any(x in article_title.lower() for x in ["error", "trouble", "fail", "fix"]):
                    content_classification = "Troubleshooting"
                elif "?" in article_title:
                    content_classification = "FAQ"

                data.append({
                    "article id": f"KB-{article_id}",
                    "article name": article_title,
                    "category": category_name,
                    "url": article_url,
                    "last updated": last_updated,
                    "topics covered": "",
                    "content type": content_classification,
                    "word count": word_count,
                    "has screenshots": bool_screenshots,
                    "has video": bool_video,
                    "gaps identified": "",
                    "text": full_text
                })
                print(f"{article_id}: {article_title}")
                article_id += 1
                #In case to have strictly 20 articles
                # if len(data) >= 20:
                #     return data

    return data


def llm_topics_analysis(data):
    load_dotenv()
    GEMINI_KEY = os.getenv("GEMINI_KEY")
    client = genai.Client(api_key=GEMINI_KEY)
    batch_size = 40

    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]

        prompt_items = []
        for item in batch:
            prompt_items.append(
                f"ID: {item["article id"]} | Title: {item["article name"]} | Content: {item["text"]}")
        batch_prompt = "\n".join(prompt_items)

        prompt_message = (
            """
            Act as Senior Technical Writer and QA Auditor. For each article provided, perform two distinct tasks:
            
            1. Extract 4 key technical topics (e.g. JIRA Cloud, JIRA Server, API, API Token, Webhooks, Mapping).
            
            2. Identify ONE specific 'Documentation Gap'. We will define 'Documentation Gap' as a missing piece of
            critical information that a user would need based on the article's title (e.g. an article named
            'API errors' not containing API error codes would have a gap that we can title 'Missing API error codes').
            Base your analysis on good documentation practices for software and keep the 'Documentation Gap' brief,
            never exceeding 80 characters. If no gap is found, return 'None identified'."
            
            Return ONLY a JSON object where the keys are the article ids, and the values are 'topics' and 'gap'.
            Example format: {'KB-001': {'topics': 'JIRA, Mapping', 'gap': 'Missing API token generation steps'}}
            """
        )

        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=f"{prompt_message}\n\nArticles:\n{batch_prompt}",
                config={"response_mime_type": "application/json"}
            )

            topic_map = json.loads(response.text)

            for item in batch:
                article_id = item["article id"]
                analysis = topic_map.get(article_id, {})

                item["topics covered"] = analysis.get("topics", "N/A")
                item["gaps identified"] = analysis.get("gap", "None identified") #Double fail-safe with the None

        except Exception as e:
            print(f"LLM analysis failed for batch starting at {i} because of: {e}")

    for item in data:
        item.pop("text", None)

    return data


def excel_save(path, data):
    df = pd.DataFrame(data)
    df.to_excel(path, index=False)


def main():
    load_dotenv()
    DATA_PATH = os.getenv("DATA_PATH")
    raw_scraped_data = get_articles()
    enriched_data_with_llm = llm_topics_analysis(raw_scraped_data)
    excel_save(DATA_PATH, enriched_data_with_llm)


if __name__ == "__main__":
    main()




