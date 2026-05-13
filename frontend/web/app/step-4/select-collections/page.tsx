"use client";

import { useMemo, useState, useEffect } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../../_components/EmbeddedNavigation";
import {
  getDefaultStoreId,
  getWidgetScope,
  listCollections,
  saveWidgetScope,
  type CollectionResponse
} from "../../../lib/photoshootApi";

type CollectionOption = { id: string; title: string; subtitle: string };

export default function SelectCollectionsPage() {
  const router = useEmbeddedRouter();
  const storeId = useMemo(() => getDefaultStoreId(), []);

  const [searchQuery, setSearchQuery] = useState("");
  const [newCollectionId, setNewCollectionId] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [enabledProductIds, setEnabledProductIds] = useState<string[]>([]);
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!storeId) return;
    const controller = new AbortController();
    let active = true;
    setIsLoading(true);

    Promise.all([
      getWidgetScope({ storeId, signal: controller.signal }),
      listCollections({ storeId, limit: 250, signal: controller.signal })
    ])
      .then(([scope, availableCollections]) => {
        if (!active) return;
        setSelectedIds(scope.enabled_collection_ids);
        setEnabledProductIds(scope.enabled_product_ids);
        setCollections(availableCollections);
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Failed to load collection scope.");
      })
      .finally(() => { if (active) setIsLoading(false); });

    return () => { active = false; controller.abort(); };
  }, [storeId]);

  const collectionOptions = useMemo<CollectionOption[]>(() => {
    const optionsById = new Map<string, CollectionOption>();
    collections.forEach((c) => {
      optionsById.set(c.id, { id: c.id, title: c.title || c.id, subtitle: c.handle ? `Handle: ${c.handle}` : "Collection ID" });
    });
    selectedIds.forEach((id) => {
      if (!optionsById.has(id)) optionsById.set(id, { id, title: id, subtitle: "Collection ID" });
    });
    return [...optionsById.values()];
  }, [collections, selectedIds]);

  const visibleCollections = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return collectionOptions;
    return collectionOptions.filter((c) =>
      c.id.toLowerCase().includes(q) || c.title.toLowerCase().includes(q) || c.subtitle.toLowerCase().includes(q)
    );
  }, [collectionOptions, searchQuery]);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const addCollectionId = () => {
    const normalized = newCollectionId.trim();
    if (!normalized) return;
    setSelectedIds((current) => current.includes(normalized) ? current : [...current, normalized]);
    setNewCollectionId("");
  };

  const toggleCollection = (id: string) => {
    setSelectedIds((current) => current.includes(id) ? current.filter((x) => x !== id) : [...current, id]);
  };

  const handleSave = async () => {
    if (!storeId) { router.push("/step-4/configured"); return; }
    setIsSaving(true);
    setErrorMessage("");
    try {
      await saveWidgetScope({ storeId, scopeType: "selected_collections", enabledCollectionIds: selectedIds, enabledProductIds });
      router.push("/step-4/configured");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save selected collections.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "24px 16px", background: "#f6f4f4" }}>
      <div style={{ width: "100%", maxWidth: 600, background: "#fff", borderRadius: 14, overflow: "hidden", display: "flex", flexDirection: "column", maxHeight: "90vh", boxShadow: "0 4px 24px rgba(0,0,0,0.08)", border: "1px solid rgba(0,0,0,0.05)" }}>

        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid #f0f0f0", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <EmbeddedLink
              href="/step-4"
              style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "#f3f4f6", color: "#6b7280" }}
              aria-label="Back to previous screen"
            >
              <svg viewBox="0 0 24 24" width={16} height={16}>
                <path d="M14.6 5.5L8.2 12L14.6 18.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.8" />
              </svg>
            </EmbeddedLink>
            <h1 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#1a1a1a" }}>Add Collections</h1>
          </div>
          <EmbeddedLink
            href="/step-4"
            style={{ width: 32, height: 32, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, fontWeight: 700, background: "#f3f4f6", color: "#6b7280", textDecoration: "none" }}
            aria-label="Close"
          >
            ×
          </EmbeddedLink>
        </div>

        {/* Controls */}
        <div style={{ padding: "16px 20px 12px", display: "flex", flexDirection: "column", gap: 12, flexShrink: 0 }}>
          {!storeId && <p style={{ fontSize: 13, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626", margin: 0 }}>Open the app from Shopify Admin to load and save collections.</p>}
          {isLoading && <p style={{ fontSize: 13, padding: "8px 12px", borderRadius: 8, background: "rgba(126,1,117,0.06)", color: "#7E0175", margin: 0 }}>Loading collections...</p>}
          {errorMessage && <p style={{ fontSize: 13, padding: "8px 12px", borderRadius: 8, background: "#fff1f1", color: "#dc2626", margin: 0 }}>{errorMessage}</p>}

          {/* Search */}
          <label style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px", borderRadius: 10, border: "1.5px solid #e5e5e5", background: "#fafafa" }}>
            <svg viewBox="0 0 24 24" width={15} height={15} aria-hidden style={{ color: "#9ca3af", flexShrink: 0 }}>
              <circle cx="11.2" cy="11.2" r="6.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
              <path d="M16 16L20 20" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
            </svg>
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search collections"
              aria-label="Search collections"
              style={{ flex: 1, fontSize: 13, background: "transparent", outline: "none", border: "none", color: "#1a1a1a" }}
            />
          </label>

          {/* Add by ID */}
          <div style={{ display: "flex", gap: 8 }}>
            <input
              type="text"
              value={newCollectionId}
              onChange={(e) => setNewCollectionId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addCollectionId()}
              placeholder="Paste Shopify Collection ID"
              aria-label="Collection ID"
              style={{ flex: 1, fontSize: 13, padding: "10px 12px", borderRadius: 10, border: "1.5px solid #e5e5e5", outline: "none", color: "#1a1a1a", fontFamily: "inherit" }}
            />
            <button
              type="button"
              onClick={addCollectionId}
              style={{ padding: "10px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff", flexShrink: 0, background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)", border: "none", cursor: "pointer" }}
            >
              + Add ID
            </button>
          </div>
        </div>

        {/* List */}
        <ul style={{ flex: 1, overflowY: "auto", padding: "0 20px 12px", minHeight: 0, listStyle: "none", margin: 0 }}>
          {visibleCollections.map((collection) => {
            const isSelected = selectedSet.has(collection.id);
            return (
              <li key={collection.id}>
                <button
                  type="button"
                  onClick={() => toggleCollection(collection.id)}
                  aria-pressed={isSelected}
                  style={{ width: "100%", display: "flex", alignItems: "center", gap: 12, padding: "12px", borderRadius: 10, textAlign: "left", border: "none", background: "transparent", cursor: "pointer" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "#fafafa"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  <span
                    style={{
                      width: 16, height: 16, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
                      border: isSelected ? "none" : "1.5px solid #d1d5db",
                      background: isSelected ? "linear-gradient(135deg, #7E0175, #E40206)" : "#fff",
                    }}
                  >
                    {isSelected && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#fff" }} />}
                  </span>
                  <span style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "#f3f4f6", color: "#9ca3af" }} aria-hidden>
                    <svg viewBox="0 0 24 24" width={14} height={14}>
                      <path d="M3 18H21L15.5 10.5L11 15.5L8 12L3 18Z" fill="currentColor" opacity="0.85" />
                      <circle cx="8" cy="8" r="2.1" fill="currentColor" opacity="0.85" />
                    </svg>
                  </span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: "block", fontSize: 13, fontWeight: 500, color: "#1a1a1a", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{collection.title}</span>
                    <span style={{ display: "block", fontSize: 11, color: "#9ca3af" }}>{collection.subtitle}</span>
                  </span>
                </button>
              </li>
            );
          })}
          {!isLoading && visibleCollections.length === 0 && (
            <li style={{ fontSize: 13, textAlign: "center", padding: "24px 0", color: "#9ca3af" }}>No collections found. Add a collection ID above.</li>
          )}
        </ul>

        {/* Footer */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderTop: "1px solid #f0f0f0", flexShrink: 0 }}>
          <p style={{ margin: 0, fontSize: 13, color: "#6b7280" }}>
            <strong style={{ color: "#1a1a1a" }}>{selectedIds.length}</strong> Collection{selectedIds.length === 1 ? "" : "s"} Selected
          </p>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            style={{
              padding: "9px 22px", borderRadius: 10, fontSize: 13, fontWeight: 600, color: "#fff",
              background: "linear-gradient(135deg, #7E0175 0%, #BC174A 55%, #E40206 100%)",
              border: "none",
              cursor: isSaving ? "not-allowed" : "pointer",
              opacity: isSaving ? 0.7 : 1,
            }}
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>

      </div>
    </div>
  );
}
