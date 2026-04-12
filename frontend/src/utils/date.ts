/**
 * Formats a date string to MM/DD/YYYY HH:MM (24-hour)
 * Example: 04/05/2026 19:30
 */
export const formatTaskCreationDate = (dateString: string | Date): string => {
    const date = new Date(dateString);

    if (isNaN(date.getTime())) return "Invalid Date";

    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    const yyyy = date.getFullYear();

    const hh = String(date.getHours()).padStart(2, '0');
    const min = String(date.getMinutes()).padStart(2, '0');

    return `${mm}/${dd}/${yyyy} ${hh}:${min}`;
};