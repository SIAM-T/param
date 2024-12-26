from flask import Flask, render_template, request, redirect, url_for, send_file
import os
import logging
import random
import time
import sys
import requests
from urllib.parse import urlparse, parse_qs, urlencode

app = Flask(__name__)

# Logger setup
logging.basicConfig(level=logging.INFO)

HARDCODED_EXTENSIONS = [
    ".jpg", ".jpeg", ".png", ".gif", ".pdf", ".svg", ".json",
    ".css", ".js", ".webp", ".woff", ".woff2", ".eot", ".ttf", ".otf", ".mp4", ".txt"
]

MAX_RETRIES = 3

# Load User-Agent strings
def load_user_agents():
    return [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0",
        # Add more user agents as needed
    ]

def fetch_url_content(url, proxy=None):
    """
    Fetches the content of a URL using a random user agent.
    Retries up to MAX_RETRIES times if the request fails.
    """
    user_agents = load_user_agents()
    if proxy:
        proxy = {'http': proxy, 'https': proxy}
    
    for i in range(MAX_RETRIES):
        user_agent = random.choice(user_agents)
        headers = {
            "User-Agent": user_agent
        }

        try:
            response = requests.get(url, proxies=proxy, headers=headers)
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, ValueError):
            logging.warning(f"Error fetching URL {url}. Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            logging.warning("Keyboard Interrupt received. Exiting gracefully...")
            sys.exit()

    logging.error(f"Failed to fetch URL {url} after {MAX_RETRIES} retries.")
    sys.exit()

# URL processing functions
def has_extension(url, extensions):
    parsed_url = urlparse(url)
    path = parsed_url.path
    extension = os.path.splitext(path)[1].lower()
    return extension in extensions

def clean_url(url):
    parsed_url = urlparse(url)
    if (parsed_url.port == 80 and parsed_url.scheme == "http") or (parsed_url.port == 443 and parsed_url.scheme == "https"):
        parsed_url = parsed_url._replace(netloc=parsed_url.netloc.rsplit(":", 1)[0])
    return parsed_url.geturl()

def clean_urls(urls, extensions, placeholder):
    cleaned_urls = set()
    for url in urls:
        cleaned_url = clean_url(url)
        if not has_extension(cleaned_url, extensions):
            parsed_url = urlparse(cleaned_url)
            query_params = parse_qs(parsed_url.query)
            if query_params:  # Only keep URLs with query parameters
                cleaned_params = {key: placeholder for key in query_params}
                cleaned_query = urlencode(cleaned_params, doseq=True)
                cleaned_url = parsed_url._replace(query=cleaned_query).geturl()
                cleaned_urls.add(cleaned_url)
    return list(cleaned_urls)

# Fetch and clean URLs from Wayback Machine
def fetch_and_clean_urls(domain, extensions, placeholder, proxy=None):
    logging.info(f"Fetching URLs for {domain}")
    wayback_uri = f"https://web.archive.org/cdx/search/cdx?url={domain}/*&output=txt&collapse=urlkey&fl=original&page=/"
    response = fetch_url_content(wayback_uri, proxy)
    urls = response.text.split()
    cleaned_urls = clean_urls(urls, extensions, placeholder)
    logging.info(f"Found {len(cleaned_urls)} cleaned URLs")
    return cleaned_urls

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        domain = request.form.get('domain')
        proxy = request.form.get('proxy', None)
        placeholder = request.form.get('placeholder', 'FUZZ')

        if domain:
            urls = fetch_and_clean_urls(domain, HARDCODED_EXTENSIONS, placeholder, proxy)
            return render_template('result.html', urls=urls, domain=domain)

    return render_template('index.html')

@app.route('/download/<domain>', methods=['GET'])
def download(domain):
    file_path = f"results/{domain}.txt"
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)

