# Running Wild: student guide

Your group is one survivor stranded in the wilderness. Before setting off you pack a single backpack, and then you live through 20 days of random events. Items in your backpack can protect you from those events, but you cannot carry everything. The group that plans best, survives, and finishes with the most HP wins.

This is a knapsack problem. In the GAMS exercise you build a model that chooses items to minimise expected HP loss. Use it, but think about what the model does and does not capture before you trust its answer.

## What you need

One device per group with a web browser, the app address from your instructor, the room code shown on the big screen, and your group number.

## How the session runs

1. **Join.** Open the app, choose *I am a group*, and enter the room code and your group number. Your screen confirms that you are in.
2. **Starting location.** Each group receives one of ten location cards at random. Your card appears on your screen and on the big screen. It changes how some events affect you, so read it carefully before you pack.
3. **Pack your backpack.** A timer appears on the big screen and on your device. Set a quantity for each item you want; you may take up to five copies of an item. The totals update as you go, and you cannot submit a backpack over the limits. Your choice is saved automatically: when the timer ends, your last valid backpack is submitted for you. You may also submit early, but you cannot change it afterwards.
4. **Trait card.** After every backpack is locked, each group receives a random trait card, a small advantage or handicap. Traits are drawn after packing on purpose: you cannot plan for them.
5. **The days.** Each day one event is drawn and applies to every group. The big screen shows the event, which items protect against it, and how every group's HP, water and food changed, with the reason. Your own device shows your full history.
6. **The end.** After the last day, survivors receive a bonus for the water and food they still hold, and the winner is announced.

## Your starting state and limits

| | |
|---|---|
| HP | 15 |
| Water | 6 L, plus any water you pack |
| Food | 6000 kcal, plus any food you pack |
| Weight limit | 15 kg |
| Volume limit | 60 L |

Your instructor may change these values for your class; the app always shows the ones in force.

## Events and protection

Every event has an HP change if you are not protected, and a list of items that protect you, the "Unless" column of the event table.

- "rain poncho or waterproof jacket" means either item is enough.
- "tent + sleeping bag" means you need both.
- Some events need water in hand, for example "1 L water". This means the water you actually hold that day, not the bottles you packed on day one. If you have already drunk your supply, the protection fails.
- A few events give HP, such as a hot tea by the fire, but only if you carry what they need.
- Some events find or destroy water and food.
- Carrying two copies of an item never protects you twice. Extra copies only add weight, volume, water or food.

## Food, water and cooking

Every day your group drinks 0.5 L of water and eats 500 kcal of food, and some events demand more. Rice, instant noodles and freeze-dried meals give no food at all unless you also pack a cooking pot and a stove. Some items improve what you find, for example a fishing kit for fishing.

On a few days, which nobody knows in advance, a resupply drop brings every surviving group extra water and food.

## How you can be eliminated

- Your HP falls to 0 or below.
- You end three days in a row with no water.
- You eat less than 500 kcal on ten days in a row.

An eliminated group stays on the scoreboard but takes no further part.

## Final score and winner

For each surviving group:

Final HP = HP at the end + bonus

The bonus is the number of extra days you could still survive on what you hold, set by whichever runs out first, water or food, and never more than 5. For example, 3.2 L of water lasts 6 days and 1800 kcal of food lasts 3 days, so the bonus is 3. A group holding 10 L and 16000 kcal still receives only 5.

Surviving groups rank above eliminated groups and are ordered by final HP. Eliminated groups are ordered by how long they lasted.

Carrying mountains of food and water will not win the game on its own: it leaves no room for protection, and the bonus is capped.

## Location and trait cards

Location cards change unprotected events of certain kinds, for example "unprotected wind events make you lose 2 HP more". Most location and trait effects apply only when you are not protected, which is why a backpack planned for your location reduces the luck of the draw. The exact wording on your card is the rule.

## Tips

- Read your location card before you open the item list.
- Watch both limits: some items are light but bulky.
- Check whether an item is only useful together with another.
- Ask what your GAMS model leaves out, and whether your backpack covers it.
- Agree on your backpack before the timer runs out. The app submits your last valid choice, not the one you were about to make.
