import requests
from bs4 import BeautifulSoup

class TextFetcher:
    """Class to fetch text from a given URL using Beautifulsoup API"""
    def __init__(self, url):
        self.url = url
        self.text = ""
        self.err = ""

    def fetch_text(self):
        """Fetch text from the URL and store it."""
        try:
            response = requests.get(self.url)
            response.raise_for_status()  # Raise an error for bad responses
            soup = BeautifulSoup(response.text, 'html.parser')
            self.text = ' '.join(p.get_text() for p in soup.find_all('p'))
        except requests.exceptions.RequestException as e:
            self.err = e
            return ""

