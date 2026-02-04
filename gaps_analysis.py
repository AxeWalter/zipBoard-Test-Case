import pandas as pd
from google import genai
import os
import json
from dotenv import load_dotenv


def get_gemini_client():
    load_dotenv()
    GEMINI_KEY = os.getenv("GEMINI_KEY")
    return genai.Client(api_key=GEMINI_KEY)


def generate_global_gaps(client, data_path, gaps_path):
    if not os.path.exists(data_path): #Error handling, if there is no prior data this closes
        print("Excel file not found.")
        return

    df_catalog = pd.read_excel(data_path)

    #Convert the df important attributes to string so we can feed to Gemmini
    catalog_summary = df_catalog[["article id", "category", "article name", "gaps identified"]].to_string()

    prompt = f"""
                Act as Senior Technical Writer and QA Auditor. Your task is to analyse the provided data, access the
                provided competitor websites, analyse the competitor data and compare with the provided one to, in the end,
                return 10 Global Documentation Gaps in the zipBoard documentation. I'll be more specific by parts:
                
                1. Context of what is zipBoard
                zipBoard is a Design Review & task management tool that helps teams collaborate on digital content. It's
                a central hub for content and document reviews, allowing for multiple content & document type in one place.
                
                2. Provided Data
                I already scraped the whole help center from zipBoard. The important information is: the articles id, 
                category, title and the individual gaps. This last information is important. We already ran analysis and
                have the individual gaps of each article (e.g. an article named 'API errors' not containing API error codes 
                would have a gap that we can title 'Missing API error codes'). You can use this information to infer global
                documentation gaps, like if a topic is missing in multiple articles it might be a global gap. But don't
                base yourself only on this information, use it together with the rest.
                
                Below is the current information catalog:
                {catalog_summary}
                
                3.Competitor Websites
                Compare the information found in this catalog with the information found in some competitors websites that
                provide a similar service. Think this as comparing to a possible golden standard. What documentation the
                competitor have tha zipBoard does not? What services both provide but the competitor has a more in depth
                guide on how to use? The competitors are:
                a. BugHerd (https://support.bugherd.com/en/);
                b. MarkUp.io (https://educate.ceros.com/en/collections/15677333-faq);
                c. Marker.io (https://help.marker.io/en/);
                d. Usersnap (https://help.usersnap.com/).
                
                4. Proper Description of task
                Your task is to identify 10 Global Documentation Gaps in the zipBoard documentation. These are not about
                single articles, like the 'gap' column in the catalog, but looking at the zipBoard product and finding 
                gaps in the documentations, things that could impact negatively the user, leaving them without answers. To
                do this consider all the data provided (the context, catalog and competitor), and ponder about:
                - Are there major features undocumented? (e.g. API, Security, specific integrations);
                - Are there any major user questions that are not covered in the documentation?
                - What documentation are present in the competitors website that is not available in the zipBoard?
                
                5. Output format
                Return a JSON object with a list called 'global_gaps'. Each gap must follow this EXACT table structure:
                - Gap ID: (G-001 format);
                - Category: (things like Integrations, Security, Onboarding, Developer, User, API, etc);
                - Gap Description: (1-2 sentences describing the gap);
                - Priority: (High/Medium/Low);
                - Suggested Article Title: (Catchy, helpful title);
                - Rationale: (Why this gap matters for the user, why do we need to write and article about it)
                
                Return ONLY the JSON object.
                
    """

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )

        df_gaps = pd.DataFrame(json.loads(response.text)["global_gaps"]) #Transform the JSON response into df

        if os.path.exists(gaps_path): #If the file already exists, it's overwritten. If not, it's created and named Gaps
            print(f"File exists. Overwriting 'Gaps' at {gaps_path}")
            df_gaps.to_excel(gaps_path, index=False)
        else:
            print(f"Creating new gaps report at {gaps_path}")
            df_gaps.to_excel(gaps_path, sheet_name="Gaps", index=False)

        return df_gaps #This is important so we can use the data in the other function and integrate easily

    except Exception as e:
        print(f"LLM gaps analysis failed because: {e}")


def generate_top2(client, df_gaps, gaps_path):
    if df_gaps is None or df_gaps.empty: #Same as the basic error handling of the function above
        print("No gaps spreadsheet found.")
        return

    gaps_summary = df_gaps.to_string() #This time we will use the whole df

    prompt = f"""
                Act as Senior Technical Writer and QA Auditor. Your task is to analyse the provided data and consider the
                context of zipBoard to select the top 2 gaps present in the data, provide and explanation on why they
                are the most important gaps and write and article outline for those two gaps. I'll be more specific 
                by parts:
                
                1. Context of what is zipBoard
                zipBoard is a Design Review & task management tool that helps teams collaborate on digital content. It's
                a central hub for content and document reviews, allowing for multiple content & document type in one place.
                
                2. Provided Data
                I already scraped the data from zipBoard's help center and analyzed it to the point of converging into
                the ten most important gaps in the documentation. This data I'll provide you contain the gap id, category,
                gap description, priority, suggested article title and a rationale for each individual gap. Use this
                information, together with the context and your knowledge about business, to fulfill the task.
                
                Below is the data:
                {gaps_summary}
                
                3. Proper Description of task 
                1. Select, from the provided data, the TOP 2 gaps that have the highest priority and business impact (
                e.g. blocking sales, causing high churn, causing confusion to customers). It's IMPORTANT to note: select
                the two most important gaps, not simply the first two!
                2. Provide a detailed explanation of why these two were chosen over the others and, most importantly,
                whey these are important to the customer;
                3. Write a comprehensive article outline for each gap. The outline should include:
                - Title of the article (use the one from the data provided);
                - Goal of the article;
                - Key sections (no need to write on them, just outline what should be disused);
                - Brief introduction.
                
                4. Output format
                Return a JSON object with a list called 'deep_dive' containing exactly 2 objects.
                Each object must have:
                - Gap ID: (Match the ID from the list)
                - Selection Rationale: (Why this is Top 2)
                - Article Outline: (Detailed string with sections)
                
                Return ONLY the JSON object.      
    """

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )

        df_deep_dive = pd.DataFrame(json.loads(response.text)["deep_dive"])
        #This logic allows us to work with another tab in the same gaps excel file
        with pd.ExcelWriter(gaps_path, mode="a", if_sheet_exists="replace") as writer:
            df_deep_dive.to_excel(writer, sheet_name="Top2", index=False)

    except Exception as e:
        print(f"LLM top2 analysis failed because: {e}")


def main():
    load_dotenv()
    DATA_PATH = os.getenv("DATA_PATH")
    GAPS_PATH = os.getenv("GAPS_PATH")
    client = get_gemini_client()
    gaps = generate_global_gaps(client, DATA_PATH, GAPS_PATH)
    generate_top2(client, gaps, GAPS_PATH)


if __name__ == "__main__":
    main()