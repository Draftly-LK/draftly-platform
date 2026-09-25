from src.modules.library.infrastructure import SqliteLegalCatalogue


async def test_catalogue_contains_every_statute_and_amendment() -> None:
    catalogue = SqliteLegalCatalogue()

    statutes = await catalogue.list_authorities("statute")
    amendments = await catalogue.list_authorities("amendment")

    assert len(statutes) == 57
    assert len(amendments) == 18
    assert len({item.id for item in statutes + amendments}) == 75


async def test_catalogue_searches_titles() -> None:
    rows = await SqliteLegalCatalogue().list_authorities(query="Registration of Title")

    assert [row.id for row in rows] == ["SRC011"]
