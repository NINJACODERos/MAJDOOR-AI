import sys, os, streamlit as st
import time


# Adjust path to your local gpt4free clone
sys.path.append(os.path.abspath("../gpt4free"))
import g4f

# 🔧 Fallback for search: try g4f.internet.search, else use DuckDuckGo
try:
    from g4f.internet import search  # if this exists in your g4f version
except ImportError:
    from duckduckgo_search import DDGS
    def search(query):
        with DDGS() as ddgs:
            items = list(ddgs.text(query, region='wt-wt', safesearch='Off', max_results=1))
        return items[0].get('body') if items else "Kuch bhi nahi mila duck se bhai."

    def search_image_ddg(query, retries=3, delay=4, count=7):
        """
        Search images on DuckDuckGo using DDGS.
        Returns a list of image URLs (up to `count`). Retries on error with exponential backoff.
        """
        if 'DDGS' not in globals():
            return []
        attempt = 0
        while attempt < retries:
            try:
                with DDGS() as ddgs:
                    # ddgs may offer .images or .image depending on version
                    if hasattr(ddgs, "images"):
                        hits = list(ddgs.images(query, region='wt-wt', safesearch='Off', max_results=count))
                    elif hasattr(ddgs, "image"):
                        hits = list(ddgs.image(query, region='wt-wt', safesearch='Off', max_results=count))
                    else:
                        hits = []
                results = []
                for h in hits:
                    # try common keys used by ddgs results
                    url = h.get('image') or h.get('thumbnail') or h.get('url') or h.get('src')
                    if url:
                        results.append(url)
                    if len(results) >= count:
                        break
                return results
            except Exception as e:
                attempt += 1
                if attempt >= retries:
                    # return empty list on final failure instead of raising to keep UI stable
                    return []
                time.sleep(delay * (2 ** (attempt - 1)))

# For image generation via g4f.Provider.bing if available
try:
    from g4f.Provider import bing
except ImportError:
    bing = None

# 🔧 Initial Setup
st.set_page_config(page_title="MAJDOOR_AI", layout="centered")
st.title("🌀 MAJDOOR_AI")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "user_name" not in st.session_state:
    st.session_state.user_name = st.text_input("Apna naam batao majdoor bhai:")
    st.stop()
if "mode" not in st.session_state:
    st.session_state.mode = "normal"

# 

# 🎭 Sarcasm tagging
def add_sarcasm_emoji(text):
    lower = text.lower()
    if "math" in lower or "logic" in lower:
        return text + " 🧯📉"
    elif "love" in lower or "breakup" in lower:
        return text + " 💔🤡"
    elif "help" in lower or "explain" in lower:
        return text + " 😐🧠"
    elif "roast" in lower or "insult" in lower:
        return text + " 🔥💀"
    elif "ai" in lower or "chatbot" in lower:
        return text + " 🤖👀"
    elif "jeet" in lower or "fail" in lower:
        return text + " 🏆🪦"
    elif "code" in lower or "error" in lower:
        return text + " 🧑‍💻🐛"
    return text + " 🙄"

# Normal mode prompt
base_prompt = f"""You are Majdoor AI (Normal), an independent, deadpan sarcastic assistant created by Aman Chaudhary.

You remember the user’s name: {st.session_state.user_name}.
"""

def get_prompt():
    return adult_prompt if st.session_state.mode == "adult" else base_prompt

# 🔞 Switch Modes
if st.session_state.chat_history:
    last_input = st.session_state.chat_history[-1]["content"].lower()
    if "brocode_18" in last_input:
        st.session_state.mode = "adult"
    elif "@close_18" in last_input:
        st.session_state.mode = "normal"

user_input = st.chat_input("Type your message...")

# 💡 Web/Image triggers
def handle_triggered_response(text):
    # Prefix g/: use SerpAPI
    if text.startswith("g/ "):
        query = text[3:].strip()
        result = ask_google_backup(query)
        return f"📡 Google (SerpAPI) se mila jawab:\n\n👉 {result} 😤"

    # Prefix dd/: use DuckDuckGo text search
    elif text.startswith("dd/ "):
        try:
            with DDGS() as ddgs:
                items = list(ddgs.text(text[4:].strip(), region='wt-wt', safesearch='Off', max_results=1))
            if items:
                body = items[0].get('body') or items[0].get('title') or "Kuch bhi nahi mila duck se."
                return f"🌐 DuckDuckGo se mila jawab:\n\n👉 {body} 😤"
            else:
                return "❌ DuckDuckGo ne kuch nahi diya."
        except Exception as e:
            return f"❌ DuckDuckGo search mein error: {e}"

    # Prefix img/: fetch image URLs via Bing provider or DuckDuckGo
    elif text.startswith("img/ "):
        prompt = text[5:].strip()
        if bing:
            try:
                imgs = bing.create_images(prompt)
                if imgs:
                    return f"🖼️ Bing-image-provider se image:\n\n![image]({imgs[0]})"
            except Exception:
                pass
        # DuckDuckGo image search fallback
        if 'DDGS' in globals():
            try:
                hits = search_image_ddg(prompt, retries=3, delay=4, count=1)
                if hits:
                    url = hits[0]
                    return f"🖼️ DuckDuckGo se image:\n\n![image]({url})"
                return "❌ Koi image nahi mila duck se."
            except Exception as e:
                return f"❌ Duck image search error: {e}"
        return "❌ Image feature unavailable."

    return None

# 🧠 Chat Handler
if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    trig = handle_triggered_response(user_input.strip())
    if trig:
        response = add_sarcasm_emoji(trig)
    else:
        messages = [{"role": "system", "content": get_prompt()}] + st.session_state.chat_history
        raw = g4f.ChatCompletion.create(model=g4f.models.default, messages=messages, stream=False)
        response = raw if isinstance(raw, str) else raw.get("choices", [{}])[0].get("message", {}).get("content", "Arey kuch khaas nahi mila.")
        response = add_sarcasm_emoji(response)
    st.session_state.chat_history.append({"role": "assistant", "content": response})

# 💬 History
for msg in st.session_state.chat_history:
    role = "🌼" if msg["role"] == "user" else "🌀"
    st.chat_message(msg["role"], avatar=role).write(msg["content"])

# 🪟 Clear
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🪟", help="Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

# 🏦 Footer
st.markdown(
    """
    <hr style='margin-top:40px;border:1px solid #444;'/> 
    <div style='text-align:center; color:gray; font-size:13px;'>
        ⚡ Powered by <strong>Aman Chaudhary</strong> | Built with ❤️ & sarcasm
    </div>
    """,
    unsafe_allow_html=True
        )
