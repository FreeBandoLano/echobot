"""Parish name normalization for Barbados geography.

Handles transcription variations of Barbados parish names from audio recordings.
"""

import re
from typing import Optional, List, Tuple

class ParishNormalizer:
    """Normalizes Barbados parish names from transcription variations."""

    # Official 11 parishes of Barbados
    OFFICIAL_PARISHES = [
        "St. Lucy",
        "St. Andrew",
        "St. Peter",
        "St. John",
        "St. Joseph",
        "St. Philip",
        "St. George",
        "St. Thomas",
        "St. Michael",
        "St. James",
        "Christ Church"
    ]

    # Common transcription variations and their normalized forms
    PARISH_VARIATIONS = {
        # St. Lucy variations
        "st lucie": "St. Lucy",
        "saint lucie": "St. Lucy",
        "st lucy": "St. Lucy",
        "saint lucy": "St. Lucy",
        "st. lucie": "St. Lucy",
        "saint. lucy": "St. Lucy",

        # St. Andrew variations
        "st andrew": "St. Andrew",
        "saint andrew": "St. Andrew",
        "st. andrew": "St. Andrew",
        "st andrews": "St. Andrew",
        "saint andrews": "St. Andrew",

        # St. Peter variations
        "st peter": "St. Peter",
        "saint peter": "St. Peter",
        "st. peter": "St. Peter",
        "st peters": "St. Peter",

        # St. John variations
        "st john": "St. John",
        "saint john": "St. John",
        "st. john": "St. John",
        "st johns": "St. John",

        # St. Joseph variations
        "st joseph": "St. Joseph",
        "saint joseph": "St. Joseph",
        "st. joseph": "St. Joseph",
        "st joe": "St. Joseph",

        # St. Philip variations
        "st philip": "St. Philip",
        "saint philip": "St. Philip",
        "st. philip": "St. Philip",
        "st phillips": "St. Philip",

        # St. George variations
        "st george": "St. George",
        "saint george": "St. George",
        "st. george": "St. George",

        # St. Thomas variations
        "st thomas": "St. Thomas",
        "saint thomas": "St. Thomas",
        "st. thomas": "St. Thomas",

        # St. Michael variations
        "st michael": "St. Michael",
        "saint michael": "St. Michael",
        "st. michael": "St. Michael",
        "st michaels": "St. Michael",

        # St. James variations
        "st james": "St. James",
        "saint james": "St. James",
        "st. james": "St. James",

        # Christ Church variations
        "christ church": "Christ Church",
        "christchurch": "Christ Church",
        "christ's church": "Christ Church"
    }

    # Location-to-parish mappings (common neighborhoods/areas mentioned in transcripts)
    LOCATION_TO_PARISH = {
        # St. Michael (capital city areas)
        "bridgetown": "St. Michael",
        "the city": "St. Michael",
        "belleville": "St. Michael",
        "fontabelle": "St. Michael",
        "kingsland": "St. Michael",
        "bay street": "St. Michael",
        "roebuck street": "St. Michael",
        "cheapside": "St. Michael",
        "nelson street": "St. Michael",

        # Christ Church (south coast tourist areas)
        "oistins": "Christ Church",
        "worthing": "Christ Church",
        "dover": "Christ Church",
        "st lawrence gap": "Christ Church",
        "hastings": "Christ Church",
        "rockley": "Christ Church",

        # St. James (west coast)
        "holetown": "St. James",
        "sandy lane": "St. James",
        "paynes bay": "St. James",
        "fitts village": "St. James",

        # St. Philip (east coast)
        "sam lord's castle": "St. Philip",
        "crane beach": "St. Philip",
        "ragged point": "St. Philip",

        # St. Lucy (north coast)
        "north point": "St. Lucy",
        "gay's cove": "St. Lucy",

        # St. Peter (northwest)
        "speightstown": "St. Peter",
        "six mens": "St. Peter",

        # St. Andrew (northeast)
        "belleplaine": "St. Andrew",
        "chalky mount": "St. Andrew",

        # St. Joseph (east)
        "bathsheba": "St. Joseph",
        "cattlewash": "St. Joseph",

        # St. John (central east)
        "hackleton's cliff": "St. John",
        "codrington college": "St. John",

        # St. George (central)
        "bulkeley": "St. George",
        "glebe land": "St. George",

        # St. Thomas (central)
        "welchman hall": "St. Thomas",
        "harrison's cave": "St. Thomas"
    }

    def __init__(self):
        """Initialize the parish normalizer."""
        # Build compiled regex patterns for efficient matching
        self._parish_patterns = []
        for variation, official in self.PARISH_VARIATIONS.items():
            # Create case-insensitive pattern with word boundaries
            pattern = re.compile(r'\b' + re.escape(variation) + r'\b', re.IGNORECASE)
            self._parish_patterns.append((pattern, official))

        self._location_patterns = []
        for location, parish in self.LOCATION_TO_PARISH.items():
            pattern = re.compile(r'\b' + re.escape(location) + r'\b', re.IGNORECASE)
            self._location_patterns.append((pattern, location, parish))

    def normalize(self, text: str) -> Optional[str]:
        """Normalize a parish name from transcription text.

        Args:
            text: Raw text that may contain a parish name

        Returns:
            Official parish name if found, None otherwise
        """
        if not text:
            return None

        text_lower = text.lower().strip()

        # Direct lookup in variations map
        if text_lower in self.PARISH_VARIATIONS:
            return self.PARISH_VARIATIONS[text_lower]

        # Check location-to-parish mappings
        if text_lower in self.LOCATION_TO_PARISH:
            return self.LOCATION_TO_PARISH[text_lower]

        # Try pattern matching for variations
        for pattern, official in self._parish_patterns:
            if pattern.search(text):
                return official

        return None

    def extract_parishes(self, text: str) -> List[Tuple[str, str, str]]:
        """Extract all parish mentions from text with context.

        Args:
            text: Full text to search for parish mentions

        Returns:
            List of tuples: (normalized_parish, raw_mention, context_snippet)
        """
        if not text:
            return []

        results = []

        # Extract parish name variations
        for pattern, official in self._parish_patterns:
            for match in pattern.finditer(text):
                raw_mention = match.group(0)
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                results.append((official, raw_mention, context))

        # Extract location-based parish mentions
        for pattern, location, parish in self._location_patterns:
            for match in pattern.finditer(text):
                raw_mention = match.group(0)
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                results.append((parish, raw_mention, context))

        # Remove duplicates while preserving order
        seen = set()
        unique_results = []
        for item in results:
            if item not in seen:
                seen.add(item)
                unique_results.append(item)

        return unique_results

    def is_valid_parish(self, parish_name: str) -> bool:
        """Check if a parish name is one of the 11 official parishes.

        Args:
            parish_name: Parish name to validate

        Returns:
            True if valid official parish name
        """
        return parish_name in self.OFFICIAL_PARISHES

    def get_all_parishes(self) -> List[str]:
        """Get list of all 11 official parishes.

        Returns:
            List of official parish names
        """
        return self.OFFICIAL_PARISHES.copy()


# Global normalizer instance
parish_normalizer = ParishNormalizer()


if __name__ == "__main__":
    # Test cases
    test_cases = [
        "St. Lucie",
        "bridgetown",
        "Oistins market",
        "problems in st michael",
        "holetown traffic",
        "Christ Church development"
    ]

    print("Parish Normalizer Test Cases:")
    print("=" * 60)

    for test in test_cases:
        normalized = parish_normalizer.normalize(test)
        print(f"Input: {test:30} -> {normalized}")

    print("\n" + "=" * 60)
    print("\nExtraction Test:")
    sample_text = """
    The caller from St. Lucie mentioned problems with water supply.
    Residents in Bridgetown are concerned about traffic congestion.
    Issues reported in Oistins and Worthing areas as well.
    """

    parishes = parish_normalizer.extract_parishes(sample_text)
    for parish, raw, context in parishes:
        print(f"\nParish: {parish}")
        print(f"Raw mention: '{raw}'")
        print(f"Context: ...{context}...")
