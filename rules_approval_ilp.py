# Approval-based multiwinner rules implemented as an integer linear
# program (ILP) with Gurobi

# Author: Martin Lackner


from committees import enough_approved_candidates, sort_committees
import score_functions as sf
try:
    import gurobipy as gb
except ImportError:
    None    # Gurobi not available


def compute_thiele_methods_ilp(profile, committeesize,
                               scorefct_str, resolute=False):

    enough_approved_candidates(profile, committeesize)
    scorefct = sf.get_scorefct(scorefct_str, committeesize)

    m = gb.Model()
    cands = list(range(profile.num_cand))

    # a binary variable indicating whether c is in the committee
    in_committee = m.addVars(profile.num_cand,
                             vtype=gb.GRB.BINARY,
                             name="in_comm")

    # a (intended binary) variable indicating
    # whether v approves at least l candidates in the committee
    utility = {}
    for v in profile.preferences:
        for l in range(1, committeesize + 1):
            utility[(v, l)] = m.addVar(ub=1.0)

    # constraint: the committee has the required size
    m.addConstr(gb.quicksum(in_committee[c] for c in cands) == committeesize)

    # constraint: utilities are consistent with actual committee
    for v in profile.preferences:
        m.addConstr(gb.quicksum(utility[v, l]
                                for l in range(1, committeesize + 1)) ==
                    gb.quicksum(in_committee[c] for c in v.approved))

    # objective: the PAV score of the committee
    m.setObjective(gb.quicksum(float(scorefct(l)) * v.weight * utility[(v, l)]
                               for v in profile.preferences
                               for l in range(1, committeesize + 1)),
                   gb.GRB.MAXIMIZE)

    m.setParam('OutputFlag', False)

    if resolute:
        m.setParam('PoolSearchMode', 0)
    else:
        # output all optimal committees
        m.setParam('PoolSearchMode', 2)
        # abort after (roughly) 100 optimal solutions
        m.setParam('PoolSolutions', 100)
        # ignore suboptimal committees
        m.setParam('PoolGap', 0)

    m.optimize()

    if m.Status != 2:
        print "Warning (" + scorefct_str + "):",
        print "solutions may be incomplete or not optimal."
        print "(Gurobi return code", m.Status, ")"

    # extract committees from model
    committees = []
    if resolute:
        committees.append([c for c in cands if in_committee[c].Xn >= 0.99])
    else:
        for sol in range(m.SolCount):
            m.setParam('SolutionNumber', sol)
            committees.append([c for c in cands if in_committee[c].Xn >= 0.99])

    committees = sort_committees(committees)

    return committees


def compute_monroe_ilp(profile, committeesize, resolute):
    enough_approved_candidates(profile, committeesize)

    # Monroe is only defined for unit weights
    if not profile.has_unit_weights():
        raise Exception("Monroe is only defined for unit weights (weight=1)")

    num_voters = len(profile.preferences)
    cands = list(range(profile.num_cand))

    # Alternative: split voters -> generate new profile with all weights = 1
    # prof2 = Profile(profile.num_cand)
    # for v in profile:
    #    for _ in range(v.weight):
    #        prof2.add_preference(DichotomousPreference(v.approved,
    #                                                   profile.num_cand))
    # total_weight = profile.voters_num()

    m = gb.Model()

    # optimization goal: variable "satisfaction"
    satisfaction = m.addVar(vtype=gb.GRB.INTEGER, name="satisfaction")

    # a list of committee members
    in_committee = m.addVars(profile.num_cand, vtype=gb.GRB.BINARY,
                             name="in_comm")
    m.addConstr(gb.quicksum(in_committee[c] for c in cands)
                == committeesize)

    # a partition of voters into committeesize many sets
    partition = m.addVars(profile.num_cand, len(profile.preferences),
                          vtype=gb.GRB.INTEGER, lb=0, name="partition")
    for i in range(len(profile.preferences)):
        # every voter has to be part of a voter partition set
        m.addConstr(gb.quicksum(partition[(j, i)]
                                for j in cands)
                    == profile.preferences[i].weight)
    for i in cands:
        # every voter set in the partition has to contain
        # at least (num_voters // committeesize) candidates
        m.addConstr(gb.quicksum(partition[(i, j)]
                                for j in range(len(profile.preferences)))
                    >= (num_voters // committeesize
                        - num_voters * (1 - in_committee[i])))
        # every voter set in the partition has to contain
        # at most ceil(num_voters/committeesize) candidates
        m.addConstr(gb.quicksum(partition[(i, j)]
                                for j in range(len(profile.preferences)))
                    <= (num_voters // committeesize
                        + bool(num_voters % committeesize)
                        + num_voters * (1 - in_committee[i])))
        # if in_committee[i] = 0 then partition[(i,j) = 0
        m.addConstr(gb.quicksum(partition[(i, j)]
                                for j in range(len(profile.preferences)))
                    <= num_voters * in_committee[i])

    m.update()

    # constraint for objective variable "satisfaction"
    m.addConstr(gb.quicksum(partition[(i, j)] *
                            (i in profile.preferences[j].approved)
                            for j in range(len(profile.preferences))
                            for i in cands)
                >= satisfaction)

    # optimization objective
    m.setObjective(satisfaction, gb.GRB.MAXIMIZE)

    # m.setParam('OutputFlag', False)

    m.setParam('OutputFlag', False)

    if resolute:
        m.setParam('PoolSearchMode', 0)
    else:
        # output all optimal committees
        m.setParam('PoolSearchMode', 2)
        # abort after (roughly) 100 optimal solutions
        m.setParam('PoolSolutions', 100)
        # ignore suboptimal committees
        m.setParam('PoolGap', 0)

    m.optimize()

    if m.Status != 2:
        print "Warning (Monroe): solutions may be incomplete or not optimal."
        print "(Gurobi return code", m.Status, ")"

    # extract committees from model
    committees = []
    if resolute:
        committees.append([c for c in cands if in_committee[c].Xn >= 0.99])
    else:
        for sol in range(m.SolCount):
            m.setParam('SolutionNumber', sol)
            committees.append([c for c in cands if in_committee[c].Xn >= 0.99])

    # if len(committees)>10:
    #    print "Warning (Monroe): more than 10 committees found;",
    #    print "returning first 10"
    #    committees = committees[:10]

    committees = sort_committees(committees)

    return committees
