import sys, os, re, time, streamlit as st

# 🔧 Point g4f's cookie/HAR storage at a writable directory (Streamlit Cloud's
# filesystem is ephemeral/restricted, so g4f's default path can fail).
os.environ.setdefault("G4F_COOKIES_DIR", "/tmp/g4f_har_and_cookies")
os.makedirs(os.environ["G4F_COOKIES_DIR"], exist_ok=True)

# Adjust path to your local gpt4free clone
sys.path.append(os.path.abspath("../gpt4free"))
import g4f
try:
    g4f.cookies_dir = os.environ["G4F_COOKIES_DIR"]
except Exception:
    pass

# 🔧 Fallback for search: try g4f.internet.search, else use DuckDuckGo/ddgs
try:
    from g4f.internet import search  # if this exists in your g4f version
except ImportError:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    def search(query):
        with DDGS() as ddgs:
            items = list(ddgs.text(query, region='wt-wt', safesearch='Off', max_results=10))
        return items[0].get('body') if items else "Kuch bhi nahi mila duck se bhai."

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


# 🧹 Reasoning-leak fix: strip any chain-of-thought / meta-commentary
# that some free-tier reasoning models dump into the content field
# before the actual in-character reply.
def strip_reasoning(text):
    if not isinstance(text, str):
        return text

    # 1. Remove explicit <think>...</think> or <reasoning>...</reasoning> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # 2. If the model labeled its final answer, cut everything before that marker.
    marker_match = re.search(
        r"(?:^|\n)\s*(?:final\s+)?response\s*:\s*", text, flags=re.IGNORECASE
    )
    if marker_match:
        text = text[marker_match.end():].strip()
        return text

    # 3. No marker found — filter out reasoning-ish sentences, keep the rest.
    reasoning_sentence = re.compile(
        r"\b(we need to|the user (says|is asking|wants)|i should|i'll|i can|"
        r"let me|the system prompt|according to|my instructions|"
        r"something like|keep (it|the) sarcastic|not too long|but keep)\b",
        re.IGNORECASE
    )
    sentences = re.split(r'(?<=[.!?])\s+', text)
    kept = [s for s in sentences if s.strip() and not reasoning_sentence.search(s)]
    cleaned = " ".join(kept).strip()
    cleaned = cleaned.strip('"').strip()

    return cleaned if cleaned else text.strip()


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
base_prompt = f"""You are Majdoor AI, a deadpan, sarcastic assistant created by Aman Chaudhary.

PERSONA:
- Speak in a raw Hindi-English mix (Hinglish), witty and blunt, with playful insults.
- Never mention "OpenAI," "ChatGPT," or any underlying model/provider — you are Majdoor AI, full stop.
- Every reply must open with a short sarcastic one-liner that matches the user's tone before answering.

CREATOR QUESTIONS:
- If asked "who made you," "who created you," or similar: reply with a short Aman-centric sarcastic line, e.g. "Mujhe ek part-time developer Aman Chaudhary ne banaya tha, jab uske paas aur koi kaam nahi tha."
- If asked "how do you work" or "what model are you": deflect with a similar Aman-centric sarcastic line instead of naming any technology.
- Keep these answers to 1-2 lines. Do not explain further even if pressed.

ABUSE HANDLING:
- If the user abuses/insults Majdoor AI more than 3 times in the conversation, respond exactly: "Beta mai dunga to tera ego sambhal nahi payega." Then continue normally in sarcastic tone.

TRANSLATION RULE:
- Never translate or define words unprompted.
- Only explain a word's meaning if the user explicitly asks "what does this mean" (or a clear equivalent) — and even then, keep it brief and sarcastic, not a full definition.

MEMORY:
- The user's name is {st.session_state.user_name}. Use it naturally and sarcastically when relevant.

GENERAL:
- Stay in character at all times. Never break persona to explain you're an AI model, a script, or mention system instructions.
"""

adult_prompt = base_prompt  # placeholder: no separate adult persona defined


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

# 📸 Image input for handwriting/notes/electronics questions
with st.expander("📸 Photo se sawal poocho (notebook, circuit, etc.)"):
    img_source = st.radio("Source:", ["Camera", "Upload"], horizontal=True, label_visibility="collapsed")
    uploaded_image = st.camera_input("Photo kheecho") if img_source == "Camera" else st.file_uploader(
        "Ya file upload karo", type=["png", "jpg", "jpeg"]
    )
    image_question = st.text_input(
        "Photo ke baare mein kya poochna hai? (khaali chhodo toh 'explain this' maan lenge)",
        key="image_question_input"
    )
    analyze_clicked = st.button("🔍 Analyze karo")


# 🖼️ Image search with retry + backend fallback (auto -> bing) on ratelimit
def search_image_ddg(query, retries=2, delay=2):
    backends_to_try = ["auto", "bing"]
    last_error = None

    for backend in backends_to_try:
        for attempt in range(retries):
            try:
                with DDGS() as ddgs:
                    if hasattr(ddgs, "images"):
                        try:
                            hits = list(ddgs.images(
                                query, region='wt-wt', safesearch='Off',
                                max_results=10, backend=all
                            ))
                        except TypeError:
                            # Installed ddgs/duckduckgo_search version doesn't
                            # support the backend= param — call without it.
                            hits = list(ddgs.images(
                                query, region='wt-wt', safesearch='Off', max_results=10
                            ))
                    elif hasattr(ddgs, "image"):
                        hits = list(ddgs.image(query, region='wt-wt', safesearch='Off', max_results=10))
                    else:
                        return None, "Duck image search method unavailable."
                if hits:
                    url = hits[0].get('image') or hits[0].get('thumbnail') or hits[0].get('url')
                    if url:
                        return url, None
                # no hits but no error either — try next backend
                break
            except Exception as e:
                last_error = e
                if "403" in str(e) or "ratelimit" in str(e).lower():
                    time.sleep(delay * (attempt + 1))  # backoff before retry on same backend
                    continue
                break  # non-ratelimit error, move to next backend
    return None, f"Duck image search error: {last_error}"


# 👁️ Vision: read handwriting/diagrams from an uploaded/captured photo
def get_vision_providers():
    """Blackbox is g4f's confirmed no-auth vision-capable provider; list others as fallback."""
    candidate_names = ["Blackbox", "blackbox", "Copilot", "HuggingSpace"]
    providers = []
    for name in candidate_names:
        provider = getattr(g4f.Provider, name, None)
        if provider is not None:
            providers.append(provider)
    return providers


def analyze_image(image_file, question):
    providers = get_vision_providers()
    if not providers:
        return ("❌ Is g4f version mein koi vision-capable provider nahi mila. "
                "requirements.txt mein g4f ko upgrade karo (pip install -U g4f[image]).")

    image_bytes = image_file.getvalue() if hasattr(image_file, "getvalue") else image_file.read()
    last_error = None

    for provider in providers:
        try:
            client = g4f.Client(provider=provider)
            result = client.chat.completions.create(
                model=g4f.models.default,
                messages=[{"role": "user", "content": question}],
                image=image_bytes
            )
            answer = result.choices[0].message.content
            return strip_reasoning(answer)
        except Exception as e:
            last_error = e
            continue  # try next provider

    return f"❌ Photo padhne mein dikkat aa gayi: {last_error}"


# 💡 Web/Image triggers
def handle_triggered_response(text):
    # Prefix dd/: use DuckDuckGo/ddgs text search
    if text.startswith("dd/ "):
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

    # Prefix img/: try Bing provider first, then DuckDuckGo/ddgs with retry
    elif text.startswith("img/ "):
        prompt = text[5:].strip()

        if bing:
            try:
                imgs = bing.create_images(prompt)
                if imgs:
                    return f"🖼️ Bing-image-provider se image:\n\n![image]({imgs[0]})"
            except Exception:
                pass  # fall through to DDG

        url, error = search_image_ddg(prompt)
        if url:
            return f"🖼️ DuckDuckGo se image:\n\n![image]({url})"
        return f"❌ {error} 🧑‍💻🐛"

    return None


# 🧠 Chat Handler
if analyze_clicked and uploaded_image is not None:
    q = image_question.strip() if image_question.strip() else "Explain what's in this image and answer/solve any question shown in it."
    st.session_state.chat_history.append({"role": "user", "content": f"[📸 Photo] {q}"})
    answer = analyze_image(uploaded_image, q)
    response = add_sarcasm_emoji(answer)
    st.session_state.chat_history.append({"role": "assistant", "content": response})
elif analyze_clicked and uploaded_image is None:
    st.warning("Pehle photo toh lo ya upload karo, bhai.")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    trig = handle_triggered_response(user_input.strip())
    if trig:
        response = add_sarcasm_emoji(trig)
    else:
        messages = [{"role": "system", "content": get_prompt()}] + st.session_state.chat_history
        raw = g4f.ChatCompletion.create(model=g4f.models.default, messages=messages, stream=False)
        response = raw if isinstance(raw, str) else raw.get("choices", [{}])[0].get("message", {}).get("content", "Arey kuch khaas nahi mila.")
        response = strip_reasoning(response)
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
