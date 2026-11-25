import { describe, expect, it } from "vitest";
import {
  buildVotes,
  emptyVotes,
  findKitFile,
  orderFor,
  parseKit,
  progress,
  recordAB,
  recordScore,
  shuffled,
  votesFileName,
} from "../src/lib/kit";

const config = {
  kit_id: "abc123",
  ab: [
    { id: "t1", pair: "p1", title: "Pair 1", left: "tokL", right: "tokR" },
    { id: "t2", pair: "p2", title: "Pair 2", left: "x", right: "y" },
  ],
  mushra: [{ pair: "p1", title: "Pair 1", reference: "ref", items: ["i1", "i2", "i3"] }],
  audio: { tokL: "audio/tokL.m4a", tokR: "audio/tokR.m4a", ref: "audio/ref.m4a" },
};
const html = `<html><script id="kit" type="application/json">${JSON.stringify(config).replace(/<\//g, "<\\/")}</script></html>`;

describe("listening kit", () => {
  it("parses the config that `mixconsole listen build` embeds", () => {
    const kit = parseKit(html);
    expect(kit.kit_id).toBe("abc123");
    expect(kit.ab).toHaveLength(2);
    expect(kit.mushra[0]?.items).toEqual(["i1", "i2", "i3"]);
    expect(kit.audio.tokL).toBe("audio/tokL.m4a");
  });

  it("rejects pages that are not a kit", () => {
    expect(() => parseKit("<html></html>")).toThrow(/not a MixConsole listening kit/);
    expect(() => parseKit('<script id="kit" type="application/json">[]</script>')).toThrow(
      /malformed/,
    );
  });

  it("shuffles deterministically per rater", () => {
    const kit = parseKit(html);
    expect(orderFor("ab", kit, "ann", kit.ab)).toEqual(orderFor("ab", kit, "ann", kit.ab));
    const many = Array.from({ length: 30 }, (_, i) => i);
    expect([...shuffled(many, 7)].sort((a, b) => a - b)).toEqual(many);
    expect(shuffled(many, 7)).not.toEqual(shuffled(many, 8));
  });

  it("records votes in listen-votes/v1 form", () => {
    const kit = parseKit(html);
    let votes = { ...emptyVotes(), rater: "ann" };
    votes = recordAB(votes, kit.ab[0] as never, "left");
    votes = recordAB(votes, kit.ab[0] as never, "tie");
    votes = recordScore(votes, kit.mushra[0] as never, "i1", 71.4);
    votes = recordScore(votes, kit.mushra[0] as never, "i2", 20);
    expect(progress(kit, votes)).toEqual({ ab: [1, 2], mushra: [1, 1] });
    const file = buildVotes(kit, votes, new Date("2026-01-02T03:04:05Z"));
    expect(file).toEqual({
      version: "listen-votes/v1",
      kit_id: "abc123",
      rater: "ann",
      saved: "2026-01-02T03:04:05.000Z",
      ab: [{ trial: "t1", pair: "p1", left: "tokL", right: "tokR", choice: "tie" }],
      mushra: [{ pair: "p1", scores: { i1: 71, i2: 20 } }],
    });
    expect(buildVotes(kit, emptyVotes()).rater).toBe("anonymous");
    expect(votesFileName(kit, "a b/c")).toBe("votes-a_b_c-abc123.json");
  });

  it("finds audio in the picked folder by relative path", () => {
    const file = (path: string) =>
      Object.assign(new File(["x"], path.split("/").pop() ?? "f"), { webkitRelativePath: path });
    const files = [file("kit/index.html"), file("kit/audio/tokL.m4a")];
    expect(findKitFile(files, "audio/tokL.m4a")?.name).toBe("tokL.m4a");
    expect(findKitFile(files, "audio/missing.m4a")).toBeUndefined();
  });
});
