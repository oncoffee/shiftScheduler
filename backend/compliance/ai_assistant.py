"""AI-powered compliance rule research using LiteLLM for multi-model support."""

import json
import os
import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

# LiteLLM supports 100+ models with a unified interface
# Install: pip install litellm
try:
    import litellm
    from litellm import acompletion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    acompletion = None


class ComplianceRuleSuggestionResponse(BaseModel):
    """Response from AI compliance research."""
    suggestion_id: str
    jurisdiction: str
    state_name: str
    min_rest_hours: Optional[float] = None
    minor_curfew_end: Optional[str] = None
    minor_earliest_start: Optional[str] = None
    minor_max_daily_hours: Optional[float] = None
    minor_max_weekly_hours: Optional[float] = None
    minor_age_threshold: int = 18
    daily_overtime_threshold: Optional[float] = None
    weekly_overtime_threshold: Optional[float] = None
    meal_break_after_hours: Optional[float] = None
    meal_break_duration_minutes: Optional[int] = None
    rest_break_interval_hours: Optional[float] = None
    rest_break_duration_minutes: Optional[int] = None
    advance_notice_days: Optional[int] = None
    sources: list[str] = []
    notes: Optional[str] = None
    model_used: str = ""
    created_at: datetime = None
    # Guardrail metadata
    validation_warnings: list[str] = []
    confidence_level: str = "low"  # "low", "medium", "high"
    requires_human_review: bool = True
    disclaimer: str = "AI-generated suggestions require human review and verification before use. Laws change frequently - verify with official state resources."

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Validation ranges for guardrails
VALID_RANGES = {
    "min_rest_hours": (0, 24),
    "minor_max_daily_hours": (0, 24),
    "minor_max_weekly_hours": (0, 80),
    "minor_age_threshold": (14, 21),
    "daily_overtime_threshold": (0, 24),
    "weekly_overtime_threshold": (0, 80),
    "meal_break_after_hours": (0, 12),
    "meal_break_duration_minutes": (0, 120),
    "rest_break_interval_hours": (0, 12),
    "rest_break_duration_minutes": (0, 60),
    "advance_notice_days": (0, 30),
}

# Valid time range for curfew/start times
VALID_CURFEW_RANGE = ("18:00", "23:59")  # Curfew should be evening
VALID_EARLIEST_START_RANGE = ("05:00", "08:00")  # Earliest start should be early morning


def validate_time_format(time_str: Optional[str]) -> bool:
    """Check if time string is valid HH:MM format."""
    if time_str is None:
        return True
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False


def time_in_range(time_str: str, min_time: str, max_time: str) -> bool:
    """Check if time is within expected range."""
    try:
        t = datetime.strptime(time_str, "%H:%M").time()
        min_t = datetime.strptime(min_time, "%H:%M").time()
        max_t = datetime.strptime(max_time, "%H:%M").time()
        return min_t <= t <= max_t
    except ValueError:
        return False


def validate_and_sanitize_response(data: dict) -> tuple[dict, list[str]]:
    """
    Validate and sanitize AI response data.
    Returns sanitized data and list of warnings.
    """
    warnings = []
    sanitized = data.copy()

    # Validate numeric ranges
    for field, (min_val, max_val) in VALID_RANGES.items():
        value = data.get(field)
        if value is not None:
            if not isinstance(value, (int, float)):
                warnings.append(f"{field}: Invalid type, expected number")
                sanitized[field] = None
            elif value < min_val or value > max_val:
                warnings.append(f"{field}: Value {value} outside expected range ({min_val}-{max_val})")
                # Clamp to valid range
                sanitized[field] = max(min_val, min(max_val, value))

    # Validate time formats
    for field in ["minor_curfew_end", "minor_earliest_start"]:
        value = data.get(field)
        if value is not None:
            if not validate_time_format(value):
                warnings.append(f"{field}: Invalid time format '{value}', expected HH:MM")
                sanitized[field] = None

    # Validate curfew is in evening
    if sanitized.get("minor_curfew_end"):
        if not time_in_range(sanitized["minor_curfew_end"], *VALID_CURFEW_RANGE):
            warnings.append(f"minor_curfew_end: {sanitized['minor_curfew_end']} seems unusual for a curfew time")

    # Validate earliest start is in morning
    if sanitized.get("minor_earliest_start"):
        if not time_in_range(sanitized["minor_earliest_start"], *VALID_EARLIEST_START_RANGE):
            warnings.append(f"minor_earliest_start: {sanitized['minor_earliest_start']} seems unusual for earliest start")

    # Check for required sources
    sources = data.get("sources", [])
    if not sources or len(sources) == 0:
        warnings.append("No sources provided - verification strongly recommended")
    elif all(len(s) < 10 for s in sources):
        warnings.append("Sources appear incomplete or vague")

    # Sanitize sources - remove any that look like hallucinated URLs
    valid_sources = []
    for source in sources:
        if isinstance(source, str) and len(source) > 5:
            # Flag suspicious sources
            if "example.com" in source.lower() or "placeholder" in source.lower():
                warnings.append(f"Suspicious source removed: {source[:50]}")
            else:
                valid_sources.append(source)
    sanitized["sources"] = valid_sources

    return sanitized, warnings


def calculate_confidence(data: dict, warnings: list[str]) -> str:
    """Calculate confidence level based on response quality."""
    score = 100

    # Deduct for warnings
    score -= len(warnings) * 15

    # Deduct for missing sources
    if not data.get("sources"):
        score -= 30

    # Deduct for too many null values
    null_count = sum(1 for v in data.values() if v is None)
    score -= null_count * 5

    # Deduct if notes are empty
    if not data.get("notes"):
        score -= 10

    if score >= 70:
        return "high"
    elif score >= 40:
        return "medium"
    else:
        return "low"


# US State codes and names
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def get_state_name(state_code: str) -> str:
    """Get full state name from code."""
    return US_STATES.get(state_code.upper(), state_code)


class ComplianceAIAssistant:
    """AI assistant for researching state labor laws using LiteLLM."""

    # Default models in order of preference for fallback
    DEFAULT_MODELS = [
        "gpt-4o-mini",           # OpenAI - fast and cheap
        "claude-3-haiku-20240307",  # Anthropic - fast
        "groq/llama-3.1-8b-instant",  # Groq - very fast, free tier
        "together_ai/meta-llama/Llama-3-8b-chat-hf",  # Together AI
        "ollama/llama3.1",       # Local Ollama
    ]

    def __init__(
        self,
        primary_model: Optional[str] = None,
        fallback_models: Optional[list[str]] = None,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the AI assistant.

        Args:
            primary_model: Primary model to use (env: LITELLM_MODEL)
            fallback_models: List of fallback models (env: LITELLM_FALLBACK_MODELS, comma-separated)
            api_base: Base URL for LiteLLM proxy (env: LITELLM_API_BASE)
            api_key: API key for LiteLLM proxy (env: LITELLM_API_KEY)
        """
        if not LITELLM_AVAILABLE:
            raise ImportError(
                "LiteLLM is not installed. Install with: pip install litellm"
            )

        # Get models from environment or use defaults
        self.primary_model = primary_model or os.getenv("LITELLM_MODEL", self.DEFAULT_MODELS[0])

        fallback_env = os.getenv("LITELLM_FALLBACK_MODELS", "")
        if fallback_models:
            self.fallback_models = fallback_models
        elif fallback_env:
            self.fallback_models = [m.strip() for m in fallback_env.split(",")]
        else:
            self.fallback_models = self.DEFAULT_MODELS[1:4]  # Use first few defaults

        # LiteLLM proxy configuration
        self.api_base = api_base or os.getenv("LITELLM_API_BASE")
        self.api_key = api_key or os.getenv("LITELLM_API_KEY", "")

        # When using a proxy, we don't need fallbacks - the proxy handles that
        if self.api_base:
            self.fallback_models = []

    def _get_research_prompt(self, state: str) -> str:
        """Generate the research prompt for a state."""
        state_name = get_state_name(state)
        return f"""Research {state_name} ({state}) labor laws for employee scheduling. Return ONLY a JSON object (no markdown, no explanation):

{{"state":"{state}","state_name":"{state_name}","min_rest_hours":<number or null>,"minor_curfew_end":"<HH:MM or null>","minor_earliest_start":"<HH:MM or null>","minor_max_daily_hours":<number>,"minor_max_weekly_hours":<number>,"minor_age_threshold":18,"daily_overtime_threshold":<number or null>,"weekly_overtime_threshold":40,"meal_break_after_hours":<number>,"meal_break_duration_minutes":<number>,"rest_break_interval_hours":<number or null>,"rest_break_duration_minutes":<number or null>,"advance_notice_days":<number or null>,"sources":["<citations>"],"notes":"<brief caveats>"}}

Rules:
- Use null if state follows federal defaults
- minor_curfew_end: latest time minors can work (e.g., "22:00")
- minor_earliest_start: earliest time minors can start (e.g., "06:00")
- daily_overtime_threshold: hours before daily OT (null if none, 8 for CA)
- advance_notice_days: predictive scheduling requirement (null if none)"""

    async def _call_model(self, model: str, prompt: str) -> tuple[str, str]:
        """
        Call a specific model and return the response.

        Returns:
            Tuple of (response_text, model_used)
        """
        system_prompt = """You are a legal research assistant specializing in US labor law.

CRITICAL GUIDELINES:
1. Only provide information you are confident about based on actual state laws
2. Use null for any value you are uncertain about - do not guess
3. Always cite specific law codes, statutes, or official sources
4. If a state follows federal defaults, say so explicitly
5. Do not hallucinate or make up laws - accuracy is critical for legal compliance
6. Respond ONLY with valid JSON - no markdown, no explanation text

IMPORTANT: These rules will be used for employee scheduling compliance. Incorrect information could lead to legal violations. When in doubt, use null and note uncertainty."""

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        # If using a LiteLLM proxy, use OpenAI client directly
        if self.api_base:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                base_url=self.api_base,
                api_key=self.api_key or "",  # Can be empty for local proxy
            )

            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=4096,  # Increased for longer responses
            )
            content = response.choices[0].message.content

            # Check if response was truncated
            if response.choices[0].finish_reason == "length":
                raise ValueError("Response was truncated due to length limit")

            return content, model

        # Otherwise use litellm directly (for direct provider access)
        response = await acompletion(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
        )
        return response.choices[0].message.content, model

    async def research_state_laws(self, state: str) -> ComplianceRuleSuggestionResponse:
        """
        Research labor laws for a state using AI.

        Attempts primary model first, then falls back to alternatives.

        Args:
            state: State code (e.g., "CA", "NY")

        Returns:
            ComplianceRuleSuggestionResponse with researched rules
        """
        state = state.upper()
        if state not in US_STATES and state != "DEFAULT":
            raise ValueError(f"Invalid state code: {state}")

        prompt = self._get_research_prompt(state)
        all_models = [self.primary_model] + self.fallback_models
        last_error = None

        for model in all_models:
            try:
                response_text, model_used = await self._call_model(model, prompt)
                parsed = self._parse_response(response_text, state, model_used)
                return parsed
            except Exception as e:
                last_error = e
                # Log and try next model
                print(f"Model {model} failed: {e}")
                continue

        # All models failed
        raise RuntimeError(
            f"All models failed to research state laws. Last error: {last_error}"
        )

    def _parse_response(
        self, response_text: str, state: str, model_used: str
    ) -> ComplianceRuleSuggestionResponse:
        """Parse AI response into structured suggestion."""
        if not response_text:
            raise ValueError("Empty response from AI model")

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_str = response_text.strip()
            # Find the JSON object
            start = json_str.find('{')
            end = json_str.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = json_str[start:end]
            else:
                raise ValueError(f"No JSON object found in response: {response_text[:200]}")

        # Check for truncated JSON (missing closing brace)
        if json_str.count('{') != json_str.count('}'):
            raise ValueError(f"Truncated JSON response (mismatched braces): {json_str[:200]}...")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse AI response as JSON: {e}\nResponse: {json_str[:300]}")

        # Validate and sanitize the response
        sanitized_data, warnings = validate_and_sanitize_response(data)

        # Calculate confidence level
        confidence = calculate_confidence(sanitized_data, warnings)

        # Add disclaimer based on confidence
        disclaimer = "AI-generated suggestions require human review and verification before use. Laws change frequently - verify with official state resources."
        if confidence == "low":
            disclaimer = "LOW CONFIDENCE: This response has significant issues. Manual research strongly recommended. " + disclaimer
        elif confidence == "medium":
            disclaimer = "MEDIUM CONFIDENCE: Some values may need verification. " + disclaimer

        return ComplianceRuleSuggestionResponse(
            suggestion_id=str(uuid.uuid4()),
            jurisdiction=state,
            state_name=get_state_name(state),
            min_rest_hours=sanitized_data.get("min_rest_hours"),
            minor_curfew_end=sanitized_data.get("minor_curfew_end"),
            minor_earliest_start=sanitized_data.get("minor_earliest_start"),
            minor_max_daily_hours=sanitized_data.get("minor_max_daily_hours"),
            minor_max_weekly_hours=sanitized_data.get("minor_max_weekly_hours"),
            minor_age_threshold=sanitized_data.get("minor_age_threshold", 18),
            daily_overtime_threshold=sanitized_data.get("daily_overtime_threshold"),
            weekly_overtime_threshold=sanitized_data.get("weekly_overtime_threshold", 40),
            meal_break_after_hours=sanitized_data.get("meal_break_after_hours"),
            meal_break_duration_minutes=sanitized_data.get("meal_break_duration_minutes"),
            rest_break_interval_hours=sanitized_data.get("rest_break_interval_hours"),
            rest_break_duration_minutes=sanitized_data.get("rest_break_duration_minutes"),
            advance_notice_days=sanitized_data.get("advance_notice_days"),
            sources=sanitized_data.get("sources", []),
            notes=sanitized_data.get("notes"),
            model_used=model_used,
            created_at=datetime.utcnow(),
            validation_warnings=warnings,
            confidence_level=confidence,
            requires_human_review=True,
            disclaimer=disclaimer,
        )


# Default rules for states without specific laws
DEFAULT_COMPLIANCE_RULES = {
    "min_rest_hours": 8.0,
    "minor_curfew_end": "22:00",
    "minor_earliest_start": "06:00",
    "minor_max_daily_hours": 8.0,
    "minor_max_weekly_hours": 40.0,
    "minor_age_threshold": 18,
    "daily_overtime_threshold": None,  # No federal daily OT
    "weekly_overtime_threshold": 40.0,
    "meal_break_after_hours": 6.0,
    "meal_break_duration_minutes": 30,
    "rest_break_interval_hours": 4.0,
    "rest_break_duration_minutes": 10,
    "advance_notice_days": 14,
}


def get_default_rules(state: str = "DEFAULT") -> ComplianceRuleSuggestionResponse:
    """Get default compliance rules (federal minimums)."""
    return ComplianceRuleSuggestionResponse(
        suggestion_id=str(uuid.uuid4()),
        jurisdiction=state,
        state_name="Default (Federal)" if state == "DEFAULT" else get_state_name(state),
        **DEFAULT_COMPLIANCE_RULES,
        sources=["Federal Fair Labor Standards Act (FLSA)", "Federal child labor provisions (29 CFR Part 570)"],
        notes="These are federal minimum standards. Many states have stricter requirements. Verify with your state's Department of Labor.",
        model_used="default",
        created_at=datetime.utcnow(),
        validation_warnings=[],
        confidence_level="high",
        requires_human_review=True,
        disclaimer="These are federal default rules. Your state may have stricter requirements. Always verify with official state resources before use.",
    )
