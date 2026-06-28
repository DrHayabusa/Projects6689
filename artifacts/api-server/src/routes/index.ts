import { Router } from "express";
import translateRouter from "./translate";

const router = Router();

// Lightweight liveness probe.
router.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

router.use(translateRouter);

export default router;
