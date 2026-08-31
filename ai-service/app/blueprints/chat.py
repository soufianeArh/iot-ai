"""
The chat endpoint: an agent loop over the tools in chat_tools.

The loop is the whole idea, and it is smaller than people expect:

    1. send the conversation + the tool schemas to the model
    2. if the model asked for tools -> run them, append the results, go to 1
    3. if it answered in prose -> return it

Two or three passes is typical. The cap exists because a small model that has
lost the thread will happily call the same tool forever.

The server keeps no session: the browser sends the history back each time. That
is the simplest thing that works, and it means restarting ai-service does not
drop anyone's conversation.
"""
import json
import logging

from flask import Blueprint, jsonify, request

from app.services import chat_tools, llm_client
from app.services.llm_client import LLMError

log = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)

MAX_ROUNDS = 4          # model turns per question, tool rounds included
MAX_HISTORY = 12        # messages of context kept; small models degrade past this

SYSTEM_PROMPT = """Assistant for a video-analytics system: IoT devices on MQTT,
RTSP cameras, YOLO object detection, and rules that turn detections into alerts.

- Answer ONLY from tool results. Never guess a number, name or time.
- Need data? Call a tool. Do not describe the call in words.
- Read each item's fields individually. A camera with status "UNREACHABLE" is
  NOT working; one with "REACHABLE" is. Never merge items into one claim.
- Tool returned an error? Say what failed. Do not invent a result.
- Two or three sentences, with the actual numbers.
"""


def _tool_calls(message: dict) -> list:
    """OpenAI-shaped tool calls, tolerating a model that omits the key."""
    return message.get("tool_calls") or []


@chat_bp.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    question = (body.get("message") or "").strip()
    if not question:
        return jsonify({"status": 400, "error": "Bad Request",
                        "message": "message is required"}), 400

    # History arrives from the browser as [{role, content}, ...].
    history = [m for m in (body.get("history") or [])
               if isinstance(m, dict) and m.get("role") in ("user", "assistant")
               and m.get("content")][-MAX_HISTORY:]

    messages = ([{"role": "system", "content": SYSTEM_PROMPT}]
                + [{"role": m["role"], "content": m["content"]} for m in history]
                + [{"role": "user", "content": question}])

    used = []       # what was called, surfaced to the UI so the loop is visible
    seen = {}       # tool results already fetched this turn (see below)

    try:
        for round_number in range(MAX_ROUNDS):
            message = llm_client.chat(messages, tools=chat_tools.SCHEMAS)
            messages.append(message)

            calls = _tool_calls(message)
            if not calls:
                answer = (message.get("content") or "").strip()
                if not answer:
                    answer = "The model returned an empty answer. Try rephrasing."
                return jsonify({"answer": answer, "toolsUsed": used,
                                "rounds": round_number + 1})

            for call in calls:
                function = call.get("function", {})
                name = function.get("name", "")
                raw = function.get("arguments") or "{}"
                # Ollama sends a dict here; OpenAI sends a JSON string.
                if isinstance(raw, str):
                    try:
                        arguments = json.loads(raw or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                else:
                    arguments = raw

                # gpt-oss-20b emits {"": "{}"} for a no-argument tool: the whole
                # argument object nested under an empty key. Unwrapped, it
                # dispatches as list_devices(**{"": "{}"}) and fails. The model
                # then retries correctly, but that is a wasted round trip on a
                # token budget, so normalise it here.
                if isinstance(arguments, dict) and list(arguments.keys()) == [""]:
                    inner = arguments[""]
                    try:
                        arguments = json.loads(inner) if isinstance(inner, str) else {}
                    except json.JSONDecodeError:
                        arguments = {}
                if not isinstance(arguments, dict):
                    arguments = {}

                # Models routinely re-request a tool they already called this
                # turn. Re-running it wastes a query and, on a rate-limited
                # free tier, doubles the token cost of every question. Serve
                # the cached rows and tell it to stop fetching.
                signature = (name, json.dumps(arguments, sort_keys=True, default=str))
                if signature in seen:
                    result = dict(seen[signature]) if isinstance(seen[signature], dict) \
                        else seen[signature]
                    if isinstance(result, dict):
                        result["_note"] = ("already fetched this turn - answer "
                                           "the question from this data now")
                else:
                    result = chat_tools.run(name, arguments)
                    seen[signature] = result
                    used.append({"tool": name, "arguments": arguments})

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", name),
                    "name": name,
                    "content": json.dumps(result, default=str),
                })

        # Fell out of the loop: it kept asking for tools and never concluded.
        return jsonify({
            "answer": ("I kept looking things up without reaching an answer - "
                       "that usually means the question needs to be more specific."),
            "toolsUsed": used, "rounds": MAX_ROUNDS,
        })

    except LLMError as exc:
        # 503, not 500: the service is fine, its dependency is not.
        return jsonify({"status": 503, "error": "LLM unavailable",
                        "message": str(exc)}), 503


@chat_bp.route("/chat/health", methods=["GET"])
def chat_health():
    """Separate from /ai/health on purpose: the chat being down must not make
    the container unhealthy and take inference down with it."""
    return jsonify(llm_client.health())


@chat_bp.route("/chat/tools", methods=["GET"])
def chat_tools_list():
    """What the model is allowed to do. Shown on the page - the point of the
    exercise is that this list is small, readable and entirely yours."""
    return jsonify([{
        "name": schema["function"]["name"],
        "description": schema["function"]["description"],
        "parameters": sorted((schema["function"].get("parameters") or {})
                             .get("properties", {}).keys()),
    } for schema in chat_tools.SCHEMAS])
