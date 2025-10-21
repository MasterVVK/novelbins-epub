import google.generativeai as genai
import os

#genai.configure(api_key="AIzaSyDQFynSk4rV-tSYAviGjASgSDG_fU8wLgo")
genai.configure(api_key="AIzaSyCMsmqNiBKvwzctgTisqQCGXwBH1y-IL2k")
model = genai.GenerativeModel("gemini-2.5-pro")

response = model.generate_content("Краткое описание алгоритмов кластеризации")
print(response.text)
