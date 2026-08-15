from skinflow_api.application.scan.models import ScanRequest
from skinflow_api.application.scan.ports import Candidate, CandidateSource, ScanEventSink


class ManualCandidateSource(CandidateSource):
    def list_candidates(
        self, request: ScanRequest, event_sink: ScanEventSink | None = None
    ) -> list[Candidate]:
        del event_sink
        return [
            Candidate(name, name, "", 0, 0)
            for name in request.manual_names[: request.candidate_limit]
        ]


class CombinedCandidateSource(CandidateSource):
    def __init__(self, primary: CandidateSource, manual: CandidateSource) -> None:
        self._primary = primary
        self._manual = manual

    def list_candidates(
        self, request: ScanRequest, event_sink: ScanEventSink | None = None
    ) -> list[Candidate]:
        candidates = list(self._primary.list_candidates(request, event_sink))
        candidates.extend(self._manual.list_candidates(request, event_sink))
        seen: set[str] = set()
        unique = []
        for candidate in candidates:
            if candidate.market_hash_name not in seen:
                seen.add(candidate.market_hash_name)
                unique.append(candidate)
        return unique[: request.candidate_limit]
