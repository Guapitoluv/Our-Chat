export class Search {
    search(query, items) {
        const results = {};

        if (!query) {
            return results;
        }

        const escapedQuery =
            query.replace(
                /[.*+?^${}()|[\]\\]/g,
                "\\$&"
            );
        
        const regex =
            new RegExp(
                escapedQuery,
                "gi"
            );
        
        for (const item of items) {
            results[item] = [];

            for (const match of item.matchAll(regex)) {
                const start = match.index;
                const end = start + match[0].length;

                results[item].push([start, end]);
            }
        }

        return results;
    }
}