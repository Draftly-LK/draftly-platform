# Library corpus inventory — organized reference

Companion to `library-service.md` and `corpus-governance-service.md`. This is a
**metadata-only inventory** of the research corpus (`draftly-research`,
`data/legal-sources/manifests/`). It exists so the library and corpus-governance
work can see what is available, grouped the way the curriculum groups it.

It contains titles, citation numbers, years, counts, and public source URLs. It
contains **no source text**, no raw harvest files, and no client data.

## Status: nothing here is approved for the public catalogue

Every row is `unverified` until a lawyer signs it off and
`corpus-governance-service` releases it. Per `library-service.md` §1, §6 and
§10.5, the public catalogue exposes only approved official statutes, amendments
and gazettes. The CommonLII-harvested case law below is **internal research
material only**: it must not reach the Library screen as source text, snippet,
export or download, and it is not production provenance. Section 3 records what
exists; it does not open a path to it.

Counts were read from the research manifests and are a snapshot. Regenerate from
the manifests through an approved, versioned adapter; do not copy raw data files
into this repository.

## 1. Sources by curriculum topic

Topic ids and names come from `topics.csv`. A source may appear under several
topics. Only the source count is shown per topic; the source list is in §2.

| Topic | Name | Sources |
| --- | --- | --- |
| 01 | Introduction to Conveyancing | 4 |
| 02 | Registration of Documents | 9 |
| 03 | Registration of Title | 7 |
| 04 | Condominium Property | 2 |
| 05 | Formation of Deeds | 24 |
| 06 | Drafting and Study of Instruments | 3 |
| 07 | Stamping of Deeds | 7 |
| 08 | Duties of a Notary | 4 |
| 09 | Examination of Title | 21 |
| 10 | Special Laws | 4 |
| 11 | Temple, Devala, Nindagam, Sangika, and Pudgalika Properties | 2 |
| 12 | State Lands | 12 |
| 13 | Power of Attorney | 5 |
| 14 | Last Wills | 3 |
| 15 | Trust Deeds | 2 |
| 16 | Local Authority, UDA, and Other Regulations | 10 |
| 17 | Drafting of Deeds | 25 |
| 18 | Other Related Statutory Laws | 11 |
| 19 | Case Law on Conveyancing | 3 |
| 20 | Criminal and Civil Liabilities of Notaries | 16 |

## 2. Sources by type

Grouped by `source_type` from `source-registry.csv`, oldest first. "Status" is
the research team's download state, not a legal approval state.

### Statutes (57)

| Source | Title | No. | Year | Topics | Status |
| --- | --- | --- | --- | --- | --- |
| SRC029 | Evidence Ordinance | — | 0 | 05 | downloaded |
| SRC001 | Prevention of Frauds Ordinance | 7 | 1840 | 01, 05, 06, 17 | downloaded |
| SRC058 | State Lands Encroachments Ordinance | 12 | 1840 | 12 | downloaded |
| SRC053 | Definition of Boundaries Ordinance | 1 | 1844 | 12 | downloaded |
| SRC024 | Wills Ordinance | 21 | 1844 | 05, 14, 17 | downloaded |
| SRC070 | Execution of Deeds Ordinance | 17 | 1852 | 05, 17, 18 | downloaded |
| SRC055 | Land Surveys Ordinance | 4 | 1866 | 12 | downloaded |
| SRC065 | Partnership Ordinance | 21 | 1866 | 17 | downloaded |
| SRC078 | Sannases and Old Deeds Ordinance | 6 | 1866 | 02, 09, 17, 18 | downloaded |
| SRC071 | Prescription Ordinance | 22 | 1871 | 09, 18 | downloaded |
| SRC004 | Matrimonial Rights and Inheritance Ordinance | 15 | 1876 | 01, 05, 09 | downloaded |
| SRC079 | Lands Resumption Ordinance | 4 | 1887 | 12, 18 | downloaded |
| SRC030 | Civil Procedure Code | 2 | 1889 | 05, 09, 17 | downloaded |
| SRC040 | Surveyors Ordinance | 15 | 1889 | 09 | downloaded |
| SRC017 | Powers of Attorney Ordinance | 4 | 1902 | 05, 13, 17 | downloaded |
| SRC014 | Notaries Ordinance | 1 | 1907 | 05, 06, 08, 17, 20 | downloaded |
| SRC047 | Kandyan Succession Ordinance | 23 | 1917 | 10 | downloaded |
| SRC059 | Trusts Ordinance | 9 | 1917 | 15 | downloaded |
| SRC005 | Registration of Documents Ordinance | 23 | 1927 | 02, 05, 06, 17 | downloaded |
| SRC049 | Buddhist Temporalities Ordinance | 19 | 1931 | 11, 20 | downloaded |
| SRC054 | Land Settlement Ordinance | 20 | 1931 | 12 | downloaded |
| SRC048 | Muslim Intestate Succession Ordinance | 10 | 1931 | 10 | downloaded |
| SRC057 | State Lands (Claims) Ordinance | 21 | 1931 | 12 | downloaded |
| SRC050 | Land Development Ordinance | 19 | 1935 | 12, 20 | downloaded |
| SRC044 | Bank of Ceylon Ordinance | 53 | 1938 | 09 | downloaded |
| SRC042 | Urban Councils Ordinance | 61 | 1939 | 09, 16 | downloaded |
| SRC038 | Land Registers (Reconstructed Folios) Act | 18 | 1945 | 09 | downloaded |
| SRC041 | Town and Country Planning Ordinance | 13 | 1946 | 09, 16 | downloaded |
| SRC045 | Matrimonial Rights and Inheritance (Jaffna) Ordinance | 58 | 1947 | 10 | downloaded |
| SRC061 | Municipal Councils Ordinance | 29 | 1947 | 16 | downloaded |
| SRC077 | Registration of Old Deeds and Instruments Ordinance | 35 | 1947 | 02, 09, 17, 18 | downloaded |
| SRC056 | State Lands Ordinance | 8 | 1947 | 12 | downloaded |
| SRC046 | Tesawalamai Pre-emption Ordinance | 59 | 1947 | 10 | downloaded |
| SRC064 | Mortgage Act | 6 | 1949 | 17 | downloaded |
| SRC051 | Land Acquisition Act | 9 | 1950 | 12 | downloaded |
| SRC076 | National Housing Act | 37 | 1954 | 16, 18 | downloaded |
| SRC023 | Tea and Rubber Estates (Control of Fragmentation) Act | 2 | 1958 | 05, 09, 20 | downloaded |
| SRC080 | People's Bank Act | 29 | 1961 | 17, 18 | downloaded |
| SRC073 | Local Authorities Housing Act | 14 | 1964 | 16, 18 | downloaded |
| SRC072 | Nindagama Lands Act | 30 | 1968 | 11, 12, 18 | downloaded |
| SRC033 | Land Reform Law | 1 | 1972 | 05, 12, 20 | downloaded |
| SRC028 | Rent Act | 7 | 1972 | 05, 17 | downloaded |
| SRC012 | Apartment Ownership Law | 11 | 1973 | 04, 07, 17, 20 | downloaded |
| SRC074 | State Mortgage and Investment Bank Law | 13 | 1975 | 17, 18 | downloaded |
| SRC027 | Partition Law | 21 | 1977 | 05, 17 | downloaded |
| SRC039 | Urban Development Authority Act | 41 | 1978 | 09, 16 | downloaded |
| SRC052 | Land Grants (Special Provisions) Act | 43 | 1979 | 12 | downloaded |
| SRC075 | National Housing Development Authority Act | 17 | 1979 | 16, 18 | indexed-html |
| SRC034 | Stamp Duty Act | 43 | 1982 | 05, 07, 17, 20 | downloaded |
| SRC062 | Pradeshiya Sabha Act | 15 | 1987 | 16 | downloaded |
| SRC035 | Western Province Financial Statute | 6 | 1990 | 05, 07, 20 | downloaded |
| SRC011 | Registration of Title Act | 21 | 1998 | 03, 07, 17, 20 | downloaded |
| SRC043 | Survey Act | 17 | 2002 | 09 | downloaded |
| SRC068 | Stamp Duty (Special Provisions) Act | 12 | 2006 | 07, 20 | downloaded |
| SRC031 | Companies Act | 7 | 2007 | 05, 09 | downloaded |
| SRC021 | Land (Restrictions on Alienation) Act | 38 | 2014 | 05, 09, 20 | downloaded |
| SRC037 | Revocation of Irrevocable Deeds of Gift on the Ground of Gross Ingratitude Act | 5 | 2017 | 09, 17 | downloaded |

### Amendments (18)

| Source | Title | No. | Year | Topics | Status |
| --- | --- | --- | --- | --- | --- |
| SRC032 | Companies Act Amendments | — | 0 | 05, 09 | downloaded |
| SRC006 | Registration of Documents (Amendment) Act | 5 | 1990 | 02 | downloaded |
| SRC025 | Wills (Amendment) Act | 5 | 1993 | 14 | downloaded |
| SRC069 | Stamp Duty (Special Provisions) (Amendment) Act | 10 | 2008 | 07, 20 | downloaded |
| SRC007 | Registration of Documents (Amendment) Act | 48 | 2011 | 02 | downloaded |
| SRC018 | Powers of Attorney (Amendment) Act | 14 | 2013 | 13 | downloaded |
| SRC008 | Registration of Documents (Amendment) Act | 21 | 2013 | 02 | downloaded |
| SRC013 | Apartment Ownership (Special Provisions) Act | 23 | 2018 | 04, 17 | downloaded |
| SRC022 | Land (Restrictions on Alienation) (Amendment) Act | 21 | 2018 | 05, 09, 20 | downloaded |
| SRC060 | Trusts (Amendment) Act | 6 | 2018 | 15 | downloaded |
| SRC015 | Notaries (Amendment) Act | 31 | 2022 | 05, 08, 20 | downloaded |
| SRC019 | Powers of Attorney (Amendment) Act | 28 | 2022 | 13, 17 | downloaded |
| SRC002 | Prevention of Frauds (Amendment) Act | 30 | 2022 | 01, 05, 17 | downloaded |
| SRC009 | Registration of Documents (Amendment) Act | 32 | 2022 | 02, 05 | downloaded |
| SRC026 | Wills (Amendment) Act | 29 | 2022 | 14 | downloaded |
| SRC016 | Notaries (Amendment) Act | 6 | 2024 | 05, 08, 20 | downloaded |
| SRC020 | Powers of Attorney (Amendment) Act | 3 | 2024 | 13, 17 | downloaded |
| SRC003 | Prevention of Frauds (Amendment) Act | 4 | 2024 | 01, 05, 17 | downloaded |

### Gazettes (7)

| Source | Title | No. | Year | Topics | Status |
| --- | --- | --- | --- | --- | --- |
| SRC063 | Local authority by-laws and gazettes | — | 0 | 16 | downloaded |
| SRC036 | Provincial Financial Statutes and stamp-duty gazettes | — | 0 | 07, 20 | downloaded |
| SRC087 | Registration of Title Gazette No. 1302/16 | — | 2003 | 03 | needs-official-source |
| SRC083 | Registration of Title Gazette No. 1616/23 | — | 2009 | 03 | downloaded |
| SRC084 | Registration of Title Gazette No. 1886/58 | — | 2014 | 03 | downloaded |
| SRC085 | Registration of Title Gazette No. 1912/04 | — | 2015 | 03 | downloaded |
| SRC086 | Registration of Title Gazette No. 2308/27 | — | 2022 | 03 | downloaded |

### Institution guides (3)

| Source | Title | No. | Year | Topics | Status |
| --- | --- | --- | --- | --- | --- |
| SRC082 | Conveyancing institution source pack | — | 0 | 09, 16 | indexed-reference |
| SRC081 | Registrar General's Department guides and forms | — | 0 | 02, 03, 08, 09, 13, 17 | indexed-reference |
| SRC010 | Registration of Documents Regulations | — | 1928 | 02 | downloaded |

### Case-law references (3)

| Source | Title | No. | Year | Topics | Status |
| --- | --- | --- | --- | --- | --- |
| SRC089 | Conveyancing case-law topic index | — | 0 | 19 | indexed-reference |
| SRC066 | New Law Reports | — | 0 | 19 | downloaded |
| SRC067 | Sri Lanka Law Reports | — | 0 | 19 | downloaded |

### Textbooks (1)

| Source | Title | No. | Year | Topics | Status |
| --- | --- | --- | --- | --- | --- |
| SRC088 | Required textbooks bibliography | — | 0 | — | bibliographic-only |

### Curriculum terms (1)

| Source | Title | No. | Year | Topics | Status |
| --- | --- | --- | --- | --- | --- |
| SRC090 | CRS curriculum reference | — | 0 | 09 | needs-manual-review |

## 3. Case law (internal research only)

Harvested from CommonLII and the court websites. Not exposed by the library.

### 3.1 CommonLII index by court database

| Database | Court | Indexed cases | Years | Conveyancing-relevant |
| --- | --- | --- | --- | --- |
| LKCA | Court of Appeal / New Law Reports | 7466 | 1809–2010 | 3330 |
| LKSC | Supreme Court of Sri Lanka | 2120 | 1878–2010 | 373 |

### 3.2 Indexed cases by decade

| Decade | LKCA | LKSC | Total |
| --- | --- | --- | --- |
| 1800s | 1 | 0 | 1 |
| 1870s | 13 | 2 | 15 |
| 1880s | 13 | 0 | 13 |
| 1890s | 294 | 16 | 310 |
| 1900s | 533 | 32 | 565 |
| 1910s | 865 | 28 | 893 |
| 1920s | 864 | 47 | 911 |
| 1930s | 749 | 105 | 854 |
| 1940s | 752 | 211 | 963 |
| 1950s | 832 | 221 | 1053 |
| 1960s | 587 | 314 | 901 |
| 1970s | 306 | 149 | 455 |
| 1980s | 433 | 274 | 707 |
| 1990s | 541 | 476 | 1017 |
| 2000s | 682 | 240 | 922 |
| 2010s | 1 | 5 | 6 |

### 3.3 Judgments collected from court websites

| Court | Files |
| --- | --- |
| Court of Appeal | 2941 |
| Supreme Court | 2533 |

## 4. What would be needed to use any of this in the library

1. A signed release manifest from `corpus-governance-service` naming each
   source, its policy and its display rights (`corpus-governance-service.md`).
2. Lawyer verification of each record; the harvest itself is not provenance.
3. A decision on the topic taxonomy (`library-service.md` §10.2). The
   curriculum topics in §1 are a candidate vocabulary and are **not adopted**.
4. An approved adapter or package boundary; the backend must not read
   `../draftly-research` paths directly.
