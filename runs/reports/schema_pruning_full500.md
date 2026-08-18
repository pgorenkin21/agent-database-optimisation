# Schema pruning analysis

Generated: 2026-07-17T10:09:07.600774+00:00

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
| 1464 | student_club | 0.50 | attendance, event, income, member | income, member, budget |
| 765 | superhero | 0.50 | hero_power, superpower | superpower, alignment |
| 779 | superhero | 0.50 | hero_power, superhero | superhero, alignment |
| 671 | codebase_community | 0.50 | badges, users | badges, comments |
| 243 | toxicology | 0.50 | atom, connected | atom, bond |
| 249 | toxicology | 0.50 | atom, connected | bond, atom |
| 268 | toxicology | 0.50 | atom, connected | bond, atom |
| 5 | california_schools | 0.50 | satscores, schools | schools |
| 17 | california_schools | 0.50 | satscores, schools | schools |
| 24 | california_schools | 0.50 | frpm, satscores | schools, frpm |
| 26 | california_schools | 0.50 | frpm, schools | schools |
| 27 | california_schools | 0.50 | satscores, schools | schools, frpm |
| 39 | california_schools | 0.50 | satscores, schools | schools |
| 40 | california_schools | 0.50 | satscores, schools | schools |
| 41 | california_schools | 0.50 | satscores, schools | schools |
| 45 | california_schools | 0.50 | satscores, schools | schools |
| 46 | california_schools | 0.50 | frpm, schools | schools |
| 50 | california_schools | 0.50 | satscores, schools | schools |
| 159 | financial | 0.50 | account, client, disp, trans | client, trans |
| 192 | financial | 0.50 | account, loan | loan, client, trans, order |
| 95 | financial | 0.60 | account, client, disp, district, order | account, trans, client, district, loan |
| 189 | financial | 0.60 | account, client, disp, district, order | account, client, district, trans |
| 717 | superhero | 0.67 | hero_power, superhero, superpower | superhero, superpower |
| 1002 | formula_1 | 0.67 | driverStandings, drivers, races | drivers, constructors, circuits, races |
| 719 | superhero | 0.67 | hero_power, superhero, superpower | superhero, superpower |
| 739 | superhero | 0.67 | hero_power, superhero, superpower | superhero, superpower |
| 766 | superhero | 0.67 | attribute, hero_attribute, superhero | attribute, hero_attribute |
| 792 | superhero | 0.67 | hero_power, superhero, superpower | superpower, superhero |
| 824 | superhero | 0.67 | hero_power, superhero, superpower | superhero, superpower, alignment, attribute, colour, gender, publisher, race |
| 634 | codebase_community | 0.67 | postHistory, posts, users | posts, tags, users, badges |
| 640 | codebase_community | 0.67 | postHistory, posts, users | posts, tags, users, badges |
| 207 | toxicology | 0.67 | atom, bond, connected | bond, atom |
| 215 | toxicology | 0.67 | atom, bond, connected | bond, atom, molecule |
| 219 | toxicology | 0.67 | atom, bond, molecule | bond, molecule, connected |
| 248 | toxicology | 0.67 | atom, bond, connected | bond, molecule, atom |
| 253 | toxicology | 0.67 | atom, bond, connected | bond, atom |
| 115 | financial | 0.67 | client, district, order | client, district |
| 125 | financial | 0.67 | account, district, loan | district, loan, client |
| 137 | financial | 0.67 | account, district, loan | client, account, loan, trans |
| 138 | financial | 0.67 | client, district, order | client, district |
| 137 | financial | 0.67 | account, district, loan | client, account, loan, trans |
| 138 | financial | 0.67 | client, district, order | client, district |
| 1387 | student_club | 0.75 | budget, event, expense, member | budget, event, member, attendance |
| 723 | superhero | 0.75 | colour, hero_power, superhero, superpower | colour, superhero, superpower, alignment, attribute, gender, publisher, race |
| 730 | superhero | 0.75 | hero_power, publisher, superhero, superpower | publisher, superhero, superpower |
| 751 | superhero | 0.75 | gender, hero_power, superhero, superpower | gender, superpower, superhero |
| 825 | superhero | 0.75 | gender, hero_power, superhero, superpower | gender, superhero, superpower, alignment, attribute, colour, publisher, race |
| 129 | financial | 0.75 | account, district, order, trans | card, district, trans, account, disp, loan |
| 169 | financial | 0.75 | account, client, disp, loan | client, loan, trans, account, order |
| 94 | financial | 0.80 | account, client, disp, district, order | account, order, client, trans, district, loan |
