# Sinhala review list

Every English string added or changed on this branch, with the Sinhala draft
that was added so the Sinhala UI never shows a missing key. The drafts were
written by an AI assistant and **need a native speaker's review before the
Sinhala UI is switched on**. Compared against the branch base `6177ea6`.

Existing Sinhala strings were not touched, except where noted. Placeholders in
curly braces (for example `{count}`, `{name}`, `{days}`) and ICU plural and
select syntax must be kept as they are.

- New strings: 90
- English meaning changed: 2

## Changed English strings

| Key | Before | After | Sinhala now |
| --- | --- | --- | --- |
| `home.snapshot.needsReview` | Need your review | To review | Need your review (not changed: it is still the old English text) |
| `newMatter.create` | Create matter | Create a matter | Create matter (not changed: it is still the old English text) |

## auth

| Key | English | Sinhala draft |
| --- | --- | --- |
| `auth.brandName` | Draftly | Draftly |
| `auth.brandLine` | Drafting and matter management for Registration of Title practice. | හිමිකම් ලියාපදිංචි කිරීමේ වෘත්තීය සඳහා කෙටුම්පත් සහ කාරණා කළමනාකරණය. |
| `auth.continueWith` | Continue with {provider} | {provider} සමඟ දිගටම කරගෙන යන්න |
| `auth.or` | or | හෝ |

## shell

| Key | English | Sinhala draft |
| --- | --- | --- |
| `shell.groupWork` | Work | වැඩ |
| `shell.groupKnowledge` | Knowledge | දැනුම |
| `shell.account` | Account | ගිණුම |
| `shell.accountMenu` | Account menu | ගිණුම් මෙනුව |
| `shell.collapseSidebar` | Collapse sidebar | පැති තීරුව හකුළන්න |
| `shell.expandSidebar` | Expand sidebar | පැති තීරුව දිග හරින්න |
| `shell.sidebarShortcut` | Ctrl+\ | Ctrl+\ |

## home

| Key | English | Sinhala draft |
| --- | --- | --- |
| `home.greetingMorning` | Good morning{hasName, select, true {, {name}} other {}} | සුභ උදෑසනක්{hasName, select, true {, {name}} other {}} |
| `home.greetingAfternoon` | Good afternoon{hasName, select, true {, {name}} other {}} | සුභ දහවලක්{hasName, select, true {, {name}} other {}} |
| `home.greetingEvening` | Good evening{hasName, select, true {, {name}} other {}} | සුභ සන්ධ්‍යාවක්{hasName, select, true {, {name}} other {}} |
| `home.greetingWelcome` | Welcome{hasName, select, true {, {name}} other {}} | සාදරයෙන් පිළිගනිමු{hasName, select, true {, {name}} other {}} |
| `home.contextReview` | {count, plural, one {# matter needs your review} other {# matters need your review}} | {count, plural, one {සමාලෝචනය සඳහා කාරණා #ක් තිබේ} other {සමාලෝචනය සඳහා කාරණා #ක් තිබේ}} |
| `home.contextClear` | Nothing is waiting for your review. | සමාලෝචනය සඳහා කිසිවක් බලා නොසිටී. |
| `home.contextEmpty` | Start a matter or ask a legal question. | කාරණාවක් ආරම්භ කරන්න, නැතහොත් නීතිමය ප්‍රශ්නයක් අසන්න. |
| `home.colMatter` | Matter | කාරණාව |
| `home.colInstrument` | Instrument | ලේඛන වර්ගය |
| `home.colStatus` | Status | තත්ත්වය |
| `home.colActivity` | Last activity | අවසන් ක්‍රියාකාරකම |
| `home.colNext` | Next action | ඊළඟ ක්‍රියාව |
| `home.nextOpen` | Open | විවෘත කරන්න |
| `home.nextReview` | Review | සමාලෝචනය කරන්න |
| `home.dueOverdue` | Overdue by {days, plural, one {# day} other {# days}} | දින {days}කින් ප්‍රමාදයි |
| `home.dueToday` | Due today | අද නියමිතයි |
| `home.dueIn` | In {days, plural, one {# day} other {# days}} | දින {days}කින් |
| `home.obligationsEmpty` | Nothing due in the next 14 days. | ඉදිරි දින 14 තුළ නියමිත කිසිවක් නැත. |
| `home.comingSoon` | Coming soon | ඉක්මනින් එයි |
| `home.firstRunTitle` | Start your first matter | ඔබේ පළමු කාරණාව ආරම්භ කරන්න |
| `home.firstRunBody` | Pick the instrument you are preparing. Draftly walks you through intake, checks and drafting. | ඔබ සකස් කරන ලේඛනය තෝරන්න. ලබාගැනීම, පරීක්ෂා සහ කෙටුම්පත් කිරීම හරහා Draftly ඔබට මඟ පෙන්වයි. |
| `home.workflowDescription.transfer_sale` | Transfer ownership of land to a buyer. | ඉඩමක අයිතිය ගැනුම්කරුවෙකුට පැවරීම. |
| `home.workflowDescription.mortgage` | Secure a loan against a property. | දේපළක් උකස් කර ණයක් සුරක්ෂිත කිරීම. |
| `home.workflowDescription.mortgage_cancel` | Release a property from a mortgage that has been repaid. | ණය පියවූ උකසකින් දේපළ නිදහස් කිරීම. |
| `home.workflowDescription.lease` | Grant the use of a property for a set term. | නියමිත කාලයකට දේපළක් භාවිතයට ලබා දීම. |
| `home.workflowDescription.gift` | Transfer a property without payment. | ගෙවීමකින් තොරව දේපළක් පැවරීම. |
| `home.workflowDescription.sale_agreement` | Record an agreement to sell before the transfer. | පැවරීමට පෙර විකිණීමේ ගිවිසුමක් සටහන් කිරීම. |

## matters

| Key | English | Sinhala draft |
| --- | --- | --- |
| `matters.loadFailedHelp` | Check your connection and try again. If it keeps failing, tell your administrator. | ඔබේ සම්බන්ධතාව පරීක්ෂා කර නැවත උත්සාහ කරන්න. එය දිගටම අසාර්ථක නම් ඔබේ පරිපාලකයාට දන්වන්න. |
| `matters.retry` | Try again | නැවත උත්සාහ කරන්න |
| `matters.emptyTitle` | No matters yet | තවම කාරණා නැත |
| `matters.emptyBody` | Create a matter to start examining a title. | හිමිකම පරීක්ෂා කිරීම ආරම්භ කිරීමට කාරණාවක් සාදන්න. |
| `matters.emptyAction` | Create a matter | කාරණාවක් සාදන්න |
| `matters.noMatchTitle` | No matters match this filter | මෙම පෙරහනට ගැළපෙන කාරණා නැත |
| `matters.noMatch` | Try another filter, or show every matter. | වෙනත් පෙරහනක් උත්සාහ කරන්න, නැතහොත් සියලු කාරණා පෙන්වන්න. |
| `matters.showAll` | Show all matters | සියලු කාරණා පෙන්වන්න |
| `matters.filterLabel` | Filter matters by status | තත්ත්වය අනුව කාරණා පෙරන්න |
| `matters.filterAll` | All | සියල්ල |
| `matters.filterOpen` | Open | විවෘත |
| `matters.filterReview` | To review | සමාලෝචනයට |
| `matters.filterDrafting` | In drafting | කෙටුම්පත් කරමින් |

## research

| Key | English | Sinhala draft |
| --- | --- | --- |
| `research.loadingConversations` | Loading conversations | සංවාද පූරණය වෙමින් |
| `research.retry` | Try again | නැවත උත්සාහ කරන්න |

## activity

| Key | English | Sinhala draft |
| --- | --- | --- |
| `activity.noResultsTitle` | Nothing matches your search | ඔබේ සෙවුමට ගැළපෙන කිසිවක් නැත |
| `activity.noResultsBody` | Try a different word, or choose All artifacts. | වෙනත් වචනයක් උත්සාහ කරන්න, නැතහොත් සියලු අයිතම තෝරන්න. |
| `activity.clearSearch` | Clear search | සෙවුම ඉවත් කරන්න |
| `activity.noEventsBody` | Actions on your matters appear here as you work. | ඔබ වැඩ කරන විට ඔබේ කාරණා පිළිබඳ ක්‍රියා මෙහි පෙනේ. |

## library

| Key | English | Sinhala draft |
| --- | --- | --- |
| `library.offlineTitle` | Legal sources need a server connection | නීතිමය මූලාශ්‍රවලට සේවාදායක සම්බන්ධතාවක් අවශ්‍යයි |
| `library.offlineBody` | This workspace is running offline with sample data, so the legal corpus is not available. Connect it to the Draftly server to browse the Acts and amendments. | මෙම වැඩබිම නියැදි දත්ත සමඟ නොබැඳිව ක්‍රියාත්මක වන බැවින් නීතිමය සංග්‍රහය නොමැත. පනත් සහ සංශෝධන බැලීමට එය Draftly සේවාදායකයට සම්බන්ධ කරන්න. |
| `library.retry` | Try again | නැවත උත්සාහ කරන්න |
| `library.loadFailedHelp` | Check your connection and try again. If it keeps failing, tell your administrator. | ඔබේ සම්බන්ධතාව පරීක්ෂා කර නැවත උත්සාහ කරන්න. එය දිගටම අසාර්ථක නම් ඔබේ පරිපාලකයාට දන්වන්න. |
| `library.noResultsHelp` | Try a different word, or clear the search and the filter. | වෙනත් වචනයක් උත්සාහ කරන්න, නැතහොත් සෙවුම සහ පෙරහන ඉවත් කරන්න. |
| `library.clearFilters` | Clear search and filter | සෙවුම සහ පෙරහන ඉවත් කරන්න |

## kitchen (development-only component page)

| Key | English | Sinhala draft |
| --- | --- | --- |
| `kitchen.ghost` | Ghost action | පසුබිම් රහිත ක්‍රියාව |
| `kitchen.destructive` | Destructive action | ඉවත් කිරීමේ ක්‍රියාව |
| `kitchen.small` | Small action | කුඩා ක්‍රියාව |
| `kitchen.loading` | Saving | සුරකිමින් |
| `kitchen.fields` | Form fields | පෝරම ක්ෂේත්‍ර |
| `kitchen.fieldLabel` | Matter reference | කාරණා යොමුව |
| `kitchen.fieldHelp` | As printed on the cover sheet. | ආවරණ පත්‍රයේ මුද්‍රිත පරිදි. |
| `kitchen.fieldError` | Enter a reference like RTA-2026-ABC-0001. | RTA-2026-ABC-0001 වැනි යොමුවක් ඇතුළත් කරන්න. |
| `kitchen.selectLabel` | Instrument | ලේඛනය |
| `kitchen.selectOption` | Transfer by sale | විකිණීමෙන් මාරු කිරීම |
| `kitchen.textareaLabel` | Notes | සටහන් |
| `kitchen.chips` | Status chips | තත්ත්ව ලේබල |
| `kitchen.toneNeutral` | Not started | ආරම්භ කර නැත |
| `kitchen.toneSuccess` | Confirmed | තහවුරු කළා |
| `kitchen.toneWarning` | Needs attention | අවධානය අවශ්‍යයි |
| `kitchen.toneDanger` | Blocked | අවහිරයි |
| `kitchen.toneInfo` | In progress | සිදුවෙමින් පවතී |
| `kitchen.emptyTitle` | No documents yet | තවම ලේඛන නැත |
| `kitchen.emptyBody` | Upload the title deed to begin the examination. | පරීක්ෂාව ආරම්භ කිරීමට හිමිකම් ඔප්පුව උඩුගත කරන්න. |
| `kitchen.emptyAction` | Upload a document | ලේඛනයක් උඩුගත කරන්න |
| `kitchen.menus` | Menu | මෙනුව |
| `kitchen.menuLabel` | Open the actions menu | ක්‍රියා මෙනුව විවෘත කරන්න |
| `kitchen.menuRename` | Rename | නම වෙනස් කරන්න |
| `kitchen.menuArchive` | Archive | සංරක්ෂණය කරන්න |
| `kitchen.rows` | List rows | ලැයිස්තු පේළි |
| `kitchen.rowReview` | Review required | සමාලෝචනය අවශ්‍යයි |
| `kitchen.rowOpen` | Open matter | කාරණාව විවෘත කරන්න |
