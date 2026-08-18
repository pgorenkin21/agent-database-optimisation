# Schema pruning analysis

Generated: 2026-07-17T10:09:16.410112+00:00

Heuristic: score tables from question+evidence keywords, expand FK neighbors, include matched column descriptions only.

- Tasks: **500**
- Full gold-table recall: **89.6%** (448/500)
- Avg schema size reduction: **29.4%**
- Avg tables kept: **4.4**
- Full-schema fallbacks: **116**

## Misses (gold table not in pruned schema)

| question_id | db_id | recall | gold | selected |
|------------:|-------|-------:|------|----------|
| 25 | california_schools | 0.00 | frpm, satscores | schools |
| 186 | financial | 0.25 | account, client, disp, district | client, card |
| 1464 | student_club | 0.50 | attendance, event, income, member | income, budget, member |
| 765 | superhero | 0.50 | hero_power, superpower | superpower, alignment |
| 779 | superhero | 0.50 | hero_power, superhero | superhero, alignment |
| 671 | codebase_community | 0.50 | badges, users | badges, comments |
| 243 | toxicology | 0.50 | atom, connected | atom, bond |
| 249 | toxicology | 0.50 | atom, connected | bond, atom |
| 268 | toxicology | 0.50 | atom, connected | bond, atom |
| 5 | california_schools | 0.50 | satscores, schools | schools |
| 17 | california_schools | 0.50 | satscores, schools | schools |
| 24 | california_schools | 0.50 | frpm, satscores | frpm, schools |
| 26 | california_schools | 0.50 | frpm, schools | schools |
| 27 | california_schools | 0.50 | satscores, schools | schools, frpm |
| 39 | california_schools | 0.50 | satscores, schools | schools |
| 40 | california_schools | 0.50 | satscores, schools | schools |
| 41 | california_schools | 0.50 | satscores, schools | schools |
| 45 | california_schools | 0.50 | satscores, schools | schools |
| 46 | california_schools | 0.50 | frpm, schools | schools |
| 50 | california_schools | 0.50 | satscores, schools | schools |
| 159 | financial | 0.50 | account, client, disp, trans | client, trans |
| 192 | financial | 0.50 | account, loan | trans, loan, client, order |
| 95 | financial | 0.60 | account, client, disp, district, order | district, account, loan, trans, client |
| 189 | financial | 0.60 | account, client, disp, district, order | district, client, account, trans |
| 717 | superhero | 0.67 | hero_power, superhero, superpower | superpower, superhero |
| 1002 | formula_1 | 0.67 | driverStandings, drivers, races | drivers, constructors, races, circuits |
| 719 | superhero | 0.67 | hero_power, superhero, superpower | superpower, superhero |
| 739 | superhero | 0.67 | hero_power, superhero, superpower | superpower, superhero |
| 766 | superhero | 0.67 | attribute, hero_attribute, superhero | attribute, hero_attribute |
| 792 | superhero | 0.67 | hero_power, superhero, superpower | superpower, superhero |
| 824 | superhero | 0.67 | hero_power, superhero, superpower | superpower, superhero, alignment, attribute, colour, gender, publisher, race |
| 634 | codebase_community | 0.67 | postHistory, posts, users | posts, tags, users, badges |
| 640 | codebase_community | 0.67 | postHistory, posts, users | posts, tags, users, badges |
| 207 | toxicology | 0.67 | atom, bond, connected | bond, atom |
| 215 | toxicology | 0.67 | atom, bond, connected | bond, atom, molecule |
| 219 | toxicology | 0.67 | atom, bond, molecule | bond, molecule, connected |
| 248 | toxicology | 0.67 | atom, bond, connected | bond, atom, molecule |
| 253 | toxicology | 0.67 | atom, bond, connected | bond, atom |
| 115 | financial | 0.67 | client, district, order | district, client |
| 125 | financial | 0.67 | account, district, loan | district, loan, client |
| 137 | financial | 0.67 | account, district, loan | client, loan, account, trans |
| 138 | financial | 0.67 | client, district, order | district, client |
| 137 | financial | 0.67 | account, district, loan | client, loan, account, trans |
| 138 | financial | 0.67 | client, district, order | district, client |
| 1387 | student_club | 0.75 | budget, event, expense, member | budget, event, attendance, member |
| 723 | superhero | 0.75 | colour, hero_power, superhero, superpower | colour, superpower, superhero, alignment, gender, race, publisher, attribute |
| 730 | superhero | 0.75 | hero_power, publisher, superhero, superpower | superpower, publisher, superhero |
| 751 | superhero | 0.75 | gender, hero_power, superhero, superpower | gender, superpower, superhero |
| 825 | superhero | 0.75 | gender, hero_power, superhero, superpower | gender, superpower, superhero, alignment, race, colour, publisher, attribute |
| 129 | financial | 0.75 | account, district, order, trans | card, account, trans, district, disp, loan |
| 169 | financial | 0.75 | account, client, disp, loan | client, order, account, trans, loan |
| 94 | financial | 0.80 | account, client, disp, district, order | district, order, account, client, loan, trans |
