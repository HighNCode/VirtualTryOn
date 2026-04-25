"use client";

import { useEffect, useMemo, useState } from "react";
import { EmbeddedLink, useEmbeddedRouter } from "../../../_components/EmbeddedNavigation";
import {
  getDefaultStoreId,
  getWidgetConfig,
  listCollections,
  updateWidgetConfig,
  type CollectionResponse
} from "../../../../lib/photoshootApi";

type CollectionOption = {
  id: string;
  title: string;
  subtitle: string;
};

export default function DashboardSelectCollectionsPage() {
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
    if (!storeId) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    setIsLoading(true);

    Promise.all([
      getWidgetConfig({ storeId, signal: controller.signal }),
      listCollections({ storeId, limit: 250, signal: controller.signal })
    ])
      .then(([config, availableCollections]) => {
        if (!active) {
          return;
        }

        setSelectedIds(config.enabled_collection_ids);
        setEnabledProductIds(config.enabled_product_ids);
        setCollections(availableCollections);
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) {
          return;
        }

        const message = error instanceof Error ? error.message : "Failed to load collection scope.";
        setErrorMessage(message);
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [storeId]);

  const collectionOptions = useMemo<CollectionOption[]>(() => {
    const optionsById = new Map<string, CollectionOption>();

    collections.forEach((collection) => {
      const subtitle = collection.handle ? `Handle: ${collection.handle}` : "Collection ID";

      optionsById.set(collection.id, {
        id: collection.id,
        title: collection.title || collection.id,
        subtitle
      });
    });

    selectedIds.forEach((id) => {
      if (!optionsById.has(id)) {
        optionsById.set(id, {
          id,
          title: id,
          subtitle: "Collection ID"
        });
      }
    });

    return [...optionsById.values()];
  }, [collections, selectedIds]);

  const visibleCollections = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();

    if (!normalizedQuery) {
      return collectionOptions;
    }

    return collectionOptions.filter(
      (collection) =>
        collection.id.toLowerCase().includes(normalizedQuery) ||
        collection.title.toLowerCase().includes(normalizedQuery) ||
        collection.subtitle.toLowerCase().includes(normalizedQuery)
    );
  }, [collectionOptions, searchQuery]);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const addCollectionId = () => {
    const normalized = newCollectionId.trim();

    if (!normalized) {
      return;
    }

    setSelectedIds((current) => (current.includes(normalized) ? current : [...current, normalized]));
    setNewCollectionId("");
  };

  const toggleCollection = (id: string) => {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id]
    );
  };

  const handleSave = async () => {
    if (!storeId) {
      router.push("/dashboard/manage-scope");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");

    try {
      await updateWidgetConfig({
        storeId,
        payload: {
          scope_type: "selected_collections",
          enabled_collection_ids: selectedIds,
          enabled_product_ids: enabledProductIds
        }
      });
      router.push("/dashboard/manage-scope");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to save selected collections.";
      setErrorMessage(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <main className="picker-shell">
      <section className="picker-modal" aria-label="Add Collections">
        <div className="picker-header-row">
          <EmbeddedLink href="/dashboard/manage-scope" className="picker-icon-button" aria-label="Back to manage scope">
            <svg viewBox="0 0 24 24" role="img">
              <path
                d="M14.6 5.5L8.2 12L14.6 18.5"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.8"
              />
            </svg>
          </EmbeddedLink>
          <EmbeddedLink href="/dashboard/manage-scope" className="picker-close-button" aria-label="Close">
            x
          </EmbeddedLink>
        </div>

        <h1 className="picker-title">Add Collections</h1>

        {!storeId ? <p className="ai-error-note">Open the app from Shopify Admin to load and save collections.</p> : null}
        {isLoading ? <p className="ai-status-note">Loading collections...</p> : null}
        {errorMessage ? <p className="ai-error-note">{errorMessage}</p> : null}

        <div className="picker-controls picker-controls-collections">
          <label className="picker-search-field">
            <svg viewBox="0 0 24 24" role="img" aria-hidden>
              <circle cx="11.2" cy="11.2" r="6.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
              <path d="M16 16L20 20" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
            </svg>
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search collections"
              aria-label="Search collections"
            />
          </label>
        </div>

        <div className="picker-controls picker-controls-collections">
          <label className="ai-text-field">
            <input
              type="text"
              value={newCollectionId}
              onChange={(event) => setNewCollectionId(event.target.value)}
              placeholder="Paste Shopify Collection ID"
              aria-label="Collection ID"
            />
          </label>
          <button type="button" className="picker-add-button" onClick={addCollectionId}>
            <span aria-hidden>+</span> Add ID
          </button>
        </div>

        <ul className="picker-list picker-list-collections">
          {visibleCollections.map((collection) => {
            const isSelected = selectedSet.has(collection.id);

            return (
              <li key={collection.id}>
                <button
                  type="button"
                  className="collection-row"
                  onClick={() => toggleCollection(collection.id)}
                  aria-pressed={isSelected}
                >
                  <span className={`picker-mark picker-mark-circle${isSelected ? " is-active" : ""}`} />
                  <span className="collection-thumb empty" aria-hidden>
                    <svg viewBox="0 0 24 24" role="img" aria-hidden>
                      <path d="M3 18H21L15.5 10.5L11 15.5L8 12L3 18Z" fill="currentColor" opacity="0.85" />
                      <circle cx="8" cy="8" r="2.1" fill="currentColor" opacity="0.85" />
                    </svg>
                  </span>
                  <span className="collection-copy">
                    <strong>{collection.title}</strong>
                    <span>{collection.subtitle}</span>
                  </span>
                </button>
              </li>
            );
          })}

          {!isLoading && visibleCollections.length === 0 ? (
            <li className="picker-empty">No collections found. Add a collection ID above.</li>
          ) : null}
        </ul>

        <div className="picker-footer">
          <p>
            <strong>{selectedIds.length}</strong> Collection Selected
          </p>
          <button type="button" className="picker-add-button" onClick={handleSave} disabled={isSaving}>
            <span aria-hidden>+</span> {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </section>
    </main>
  );
}
