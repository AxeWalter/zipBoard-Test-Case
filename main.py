from datetime import datetime
import schedule
import updates
import time


def job():
    updates.update_spreadsheet()
    print(f"Daily updated finished at {datetime.now():%d/%m/%Y %H:%M:%S}")


schedule.every().day.at("08:00").do(job)

if __name__ == "__main__":
    job()
    print("Running scheduled jobs...")
    while True:
        schedule.run_pending()
        time.sleep(60)