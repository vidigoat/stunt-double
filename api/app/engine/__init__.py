"""The Consequence Engine.

Everything Stunt Double decides goes through here. The engine never trusts the plan: it works only from what trusted
code measured (phase 2's effects) and from the trusted "before" copy of the data.

    graph       the Effect Graph: every consequence as a node, linked into units of work
    subsets     surgical approval: cut the wrong units out of a plan, keep the right ones
    provenance  Proof of Effect: which statement caused which change, proven by replay
    contracts   Intent Contracts: promises written before the plan, checked after it
"""
