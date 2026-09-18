# Rule audit, version 2

Reference documents: the printed event table (lists_prepared.docx), the printed location and trait cards, and the worked days in the Lecture 10 slides. Where the slides spell out a case in more detail than the printed table, the slides were followed. Every worked slide example is now an automated check in `tests/test_rules.py` (60 cases, all passing).

## 1. Event mitigation corrected to match the printed table

| Event | Before | Now |
|---|---|---|
| Blazing sun | sun hat | sun hat and at least 1 L water on hand |
| Heat surge | sun hat | sun hat and at least 1 L water on hand |
| Dry hot wind, Heat headache | any water bottle packed | at least 1 L water on hand |
| Dry throat, Nosebleed | any water bottle packed | at least 0.5 L water on hand |
| Dry lips | any water bottle packed | some water on hand |
| Heat exhaustion | any water bottle packed | at least 2 L water on hand (then HP -1, as in the slides) |
| Severe dehydration | 5 L bottle + electrolytes | electrolytes and at least 3 L water on hand (then HP -2) |
| Muscle cramp | 2 L bottle + electrolytes | electrolytes and at least 0.5 L water on hand |
| Fine afternoon, Calm warm night, Nightingale sings | +1 for everyone | +1 only with a sleeping bag |
| Mushrooms | stove or pot | stove |
| Stored water frozen | stove and pot | stove |
| Food frozen | pot or insulated container | pot |
| Foraging failure | energy bars or dry food | energy bars |
| Sore back | seat pad or ground tarp | sleeping pad (new item) |
| Scorpion sting | advanced kit only | medical kit |
| Lighter jam | matches | fire starter and lighter, or matches |
| Frozen nose, Floating ash | scarf | scarf or mask (new item) |
| Bee swarm, Bear nearby | HP -1 even with protection | 0 with protection |
| Water container torn | HP -1 | -1 L water, no HP loss |
| Broken water bag | HP -1 and -1 L | HP -1 only |

"Water on hand" means the group's current water stock at the start of the day, so the event table now links HP to the water the group has managed to keep, not only to which bottles were packed.

## 2. Location cards corrected

| Card | Issue | Now |
|---|---|---|
| Lakeside | old data made injury events worse | dehydration events are 1 HP milder, water gains x1.5 rounded up to 0.5 L |
| Valley Floor | printed card says navigation "deal an extra 1 HP (less risk of being lost)"; the slides (day 10) and GAMS reduce the damage | navigation 1 HP milder; card text on screen reworded to match |
| Valley Floor | heat exhaustion was not treated as weather | included, as in slide day 12 |
| High Plateau | severe dehydration was not a sun event | included, as in slide day 16 |
| Wind Pass | storms list included heavy rain and hail at noon | rain and snow storms only: thunderstorm, hail storm, snowstorm, torrential rain |
| Old Trail | Nightingale (+1) was not set to 0 | calm wildlife becomes 0 whatever its sign, as in slide day 5; partridge scare added to calm wildlife |
| Boggy Hollow | boiling with a stove did not count as purification | tablets, filter bottle, gravity filter or stove all count |
| Scree Slope, Glacier Ridge | cliff edge counted as slip/fall | removed; slide day 21 applies only rope and traits to it |

## 3. Items

25 items added (118 in total). Several are heavier supersets that tempt groups to spend capacity: four-season tent, winter sleeping bag, Gore-Tex shell, full wilderness medical kit. Others are light specialists (mask, head net, venom kit, balaclava), resource items with finer choices (1 L and 3 L water, pemmican, canned food, freeze-dried meals, rice), and boosters (fishing kit doubles fish; the foldable water container, previously useless, doubles rain collection and adds 50 percent to streams). Rice, instant noodles and freeze-dried meals give no food unless a pot and stove are packed.

## 4. Balance

Monte Carlo (`python calibrate.py`) showed that with 20 kg and 80 L the item set that protects best barely exceeds the limits (about 22.5 kg), so the knapsack hardly binds, and that leftover water and food converted to HP without a cap made pure stockpiling the highest-scoring strategy whenever it survived. New defaults, all adjustable when creating a room:

| Setting | Slides | New default |
|---|---|---|
| Starting HP | 20 | 15 |
| Weight / volume limit | 20 kg / 80 L | 15 kg / 60 L |
| Final-score HP from leftover water / food | uncapped | at most 5 each |
| Days | 50 | 20 |
| Resupply | none | 3 random unannounced days, +2 L water and +1500 kcal each |

Result over 20 days: random backpacks survive about 73 percent, a greedy protection-only backpack about 98 percent, and the protection-only backpack still loses groups to dehydration when resupply is switched off.
