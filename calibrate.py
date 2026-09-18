"""calibrate.py — Monte Carlo check of the default settings.
Run:  python calibrate.py
Compares a random backpack, a pure-mitigation backpack (what the GAMS
expected-HP-loss model optimises) and mitigation plus water."""
import random, statistics, engine
D=engine.load_data(); P=D["params"]
def random_pack(rng):
    ids=list(D["items"]); rng.shuffle(ids); inv={}
    for i in ids:
        inv[i]=1
        if not engine.is_feasible(inv,D,P): inv.pop(i)
    return inv
def greedy_mit(loc, water_first=0):
    # expected HP saved per kg, ignoring water unless water_first
    inv={}
    if water_first: inv={"water_5L":1,"water_2L":1,"filter_bottle":1}
    ev=D["events"]
    def gain(i):
        s=0
        for e in ev.values():
            if e["base_hp"]<=0 and i in e["mit_set"] and not engine.mitigated(inv,e):
                s+=e["weight"]*(e["mit_hp"]-e["base_hp"])
        return s/max(D["items"][i]["weight_kg"],0.05)
    while True:
        cands=[(gain(i),i) for i in D["items"] if i not in inv]
        cands=[c for c in cands if c[0]>0]
        cands.sort(reverse=True); added=False
        for g,i in cands:
            inv[i]=1
            if engine.is_feasible(inv,D,P): added=True; break
            inv.pop(i)
        if not added: break
    return inv
def run(packfn, days=20, n=400):
    alive=0; hps=[]; causes={}
    for s in range(n):
        rng=random.Random(s); loc=rng.choice(list(D["locations"])); tr=rng.choice(list(D["traits"]))
        inv=packfn(rng,loc)
        team={"inv":inv,"location":loc,"trait":tr,"state":engine.init_team_state(inv,loc,tr,D,P)}
        for d in range(1,days+1):
            engine.resolve_day(team, engine.draw_event(D,s,d), d, D,P)
        st=team["state"]
        if st["alive"]: alive+=1; hps.append(engine.final_score(st,P)["hp_final"])
        else: causes[st["death_cause"]]=causes.get(st["death_cause"],0)+1
    return alive/n, (statistics.median(hps) if hps else None), causes
if __name__ == "__main__":
  for days in (15, 20, 30):
    print("days", days)
    print(" random ", run(lambda r,l: random_pack(r),days))
    print(" mitOnly", run(lambda r,l: greedy_mit(l),days))
    print(" mit+H2O", run(lambda r,l: greedy_mit(l,1),days))
