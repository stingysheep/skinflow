from dataclasses import dataclass
from pathlib import Path

from skinflow_api.application.health import HealthService
from skinflow_api.application.inventory import InventoryService
from skinflow_api.application.ledger import LedgerService
from skinflow_api.application.listing import ListingService
from skinflow_api.application.listing.reconciliation import ListingReconciliationService
from skinflow_api.application.preferences import CsqaqConfigurationService, PreferencesStore
from skinflow_api.application.scan.service import ScanService
from skinflow_api.infrastructure.database.inventory import SqliteInventoryRepository
from skinflow_api.infrastructure.database.ledger import LedgerRepository
from skinflow_api.infrastructure.database.listing import SqliteListingRepository
from skinflow_api.infrastructure.database.sqlite_uow import SqliteScanUnitOfWork
from skinflow_api.infrastructure.platforms.buff.adapter import BuffAdapter
from skinflow_api.infrastructure.platforms.csqaq.adapter import CsqaqAdapter
from skinflow_api.infrastructure.platforms.market_detail import CsqaqMarketDetailProvider
from skinflow_api.infrastructure.platforms.market_gateway import CompositeMarketGateway
from skinflow_api.infrastructure.platforms.steam.adapter import SteamAdapter
from skinflow_api.infrastructure.platforms.steam.inventory import SteamInventoryAdapter
from skinflow_api.infrastructure.platforms.steam.listing import SteamListingAdapter
from skinflow_api.infrastructure.platforms.steam.listing_market import (
    SteamListingMarketSnapshotProvider,
)
from skinflow_api.infrastructure.platforms.steam.listing_status import SteamListingStatusAdapter
from skinflow_api.infrastructure.platforms.steam.login import SteamLoginCoordinator
from skinflow_api.infrastructure.platforms.steam.nameid_resolver import JsonNameIdResolver
from skinflow_api.infrastructure.platforms.steam.session import (
    InMemorySteamSession,
    PersistentSteamSession,
)
from skinflow_api.infrastructure.platforms.youpin import EdgeYoupinBrowser, YoupinAdapter
from skinflow_api.infrastructure.preferences import DpapiCsqaqTokenStore, JsonPreferencesStore
from skinflow_api.settings import Settings

from .listing_reconciliation_runner import ListingReconciliationRunner
from .scan_runner import ScanTaskRunner


@dataclass(frozen=True, slots=True)
class Container:
    health_service: HealthService
    scan_service: ScanService
    scan_runner: ScanTaskRunner
    ledger_service: LedgerService
    inventory_service: InventoryService
    listing_service: ListingService
    listing_reconciliation: ListingReconciliationRunner
    steam_login: SteamLoginCoordinator
    youpin_browser: EdgeYoupinBrowser
    preferences_store: PreferencesStore
    csqaq_configuration: CsqaqConfigurationService

    def close(self) -> None:
        self.listing_service.close()
        self.youpin_browser.close()
        self.preferences_store.close()


def build_container(settings: Settings) -> Container:
    persistence = SqliteScanUnitOfWork(settings.database_path)
    persistence.recover_interrupted_jobs()
    persistence.enforce_single_active_job()
    buff = BuffAdapter()
    steam = SteamAdapter()
    youpin_browser = EdgeYoupinBrowser()
    preferences_store = JsonPreferencesStore(settings.database_path)
    csqaq_token_store = DpapiCsqaqTokenStore(settings.database_path)
    youpin = YoupinAdapter(youpin_browser)
    steam_session = (
        InMemorySteamSession()
        if settings.database_path == ":memory:"
        else PersistentSteamSession(
            str(Path(settings.database_path).with_name("steam_session.bin"))
        )
    )
    listing_repository = SqliteListingRepository(settings.database_path)
    ledger_repository = LedgerRepository(settings.database_path)
    resolver = JsonNameIdResolver(settings.nameid_path)
    csqaq = CsqaqAdapter(csqaq_token_store.load() or settings.csqaq_api_token)
    csqaq_configuration = CsqaqConfigurationService(
        preferences_store,
        csqaq_token_store,
        csqaq,
        settings.csqaq_api_token,
    )
    scan_service = ScanService(
        persistence,
        csqaq,
        resolver,
        CompositeMarketGateway(buff, youpin, steam),
    )
    return Container(
        health_service=HealthService(
            service=settings.app_name,
            api_version=settings.api_version,
            environment=settings.environment,
        ),
        scan_service=scan_service,
        scan_runner=ScanTaskRunner(scan_service),
        ledger_service=LedgerService(ledger_repository),
        inventory_service=InventoryService(
            steam_session,
            SteamInventoryAdapter(steam_session),
            SqliteInventoryRepository(settings.database_path),
            CsqaqMarketDetailProvider(csqaq, resolver, steam, listing_repository),
        ),
        listing_service=ListingService(
            listing_repository,
            listing_repository,
            SteamListingAdapter(steam_session),
            SteamListingMarketSnapshotProvider(resolver, steam, listing_repository, csqaq),
        ),
        listing_reconciliation=ListingReconciliationRunner(
            ListingReconciliationService(
                listing_repository,
                SteamListingStatusAdapter(steam_session),
                ledger_repository,
            )
        ),
        steam_login=SteamLoginCoordinator(steam_session),
        youpin_browser=youpin_browser,
        preferences_store=preferences_store,
        csqaq_configuration=csqaq_configuration,
    )
